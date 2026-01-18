package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

const (
	updateInterval     = 2 * time.Second
	maxUpdateDuration  = 10 * time.Minute
	telegramMaxRunes   = 3800
	rebootCheckSeconds = 30
	dirCheckSeconds    = 30
	unitCheckSeconds   = 30
)

type Bot struct {
	token  string
	client *http.Client
}

func NewBot(token string) *Bot {
	return &Bot{
		token: token,
		client: &http.Client{
			Timeout: 40 * time.Second,
		},
	}
}

func (b *Bot) apiURL(method string) string {
	return "https://api.telegram.org/bot" + b.token + "/" + method
}

func (b *Bot) doRequest(method string, payload any, out any) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	req, err := http.NewRequest("POST", b.apiURL(method), bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := b.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return err
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("telegram error: %s", respBody)
	}

	return json.Unmarshal(respBody, out)
}

type APIResponse[T any] struct {
	OK          bool `json:"ok"`
	Result      T    `json:"result"`
	Description string `json:"description"`
}

type Update struct {
	UpdateID int      `json:"update_id"`
	Message  *Message `json:"message"`
}

type Message struct {
	MessageID int    `json:"message_id"`
	Text      string `json:"text"`
	Chat      Chat   `json:"chat"`
	From      *User  `json:"from"`
}

type Chat struct {
	ID int64 `json:"id"`
}

type User struct {
	ID int64 `json:"id"`
}

type getUpdatesRequest struct {
	Offset  int `json:"offset"`
	Timeout int `json:"timeout"`
}

func (b *Bot) GetUpdates(offset int) ([]Update, error) {
	var resp APIResponse[[]Update]
	err := b.doRequest("getUpdates", getUpdatesRequest{
		Offset:  offset,
		Timeout: 30,
	}, &resp)
	if err != nil {
		return nil, err
	}
	if !resp.OK {
		return nil, fmt.Errorf("telegram: %s", resp.Description)
	}
	return resp.Result, nil
}

type sendMessageRequest struct {
	ChatID    int64  `json:"chat_id"`
	Text      string `json:"text"`
	ParseMode string `json:"parse_mode,omitempty"`
}

type messageResult struct {
	MessageID int `json:"message_id"`
}

func (b *Bot) SendMessage(chatID int64, text string) (int, error) {
	var resp APIResponse[messageResult]
	err := b.doRequest("sendMessage", sendMessageRequest{
		ChatID:    chatID,
		Text:      trimMessage(text),
		ParseMode: "HTML",
	}, &resp)
	if err != nil {
		return 0, err
	}
	if !resp.OK {
		return 0, fmt.Errorf("telegram: %s", resp.Description)
	}
	return resp.Result.MessageID, nil
}

type editMessageRequest struct {
	ChatID    int64  `json:"chat_id"`
	MessageID int    `json:"message_id"`
	Text      string `json:"text"`
	ParseMode string `json:"parse_mode,omitempty"`
}

func (b *Bot) EditMessage(chatID int64, messageID int, text string) error {
	var resp APIResponse[bool]
	err := b.doRequest("editMessageText", editMessageRequest{
		ChatID:    chatID,
		MessageID: messageID,
		Text:      trimMessage(text),
		ParseMode: "HTML",
	}, &resp)
	if err != nil && strings.Contains(err.Error(), "message is not modified") {
		return nil
	}
	if err != nil {
		return err
	}
	if !resp.OK {
		return fmt.Errorf("telegram: %s", resp.Description)
	}
	return nil
}

type deleteMessageRequest struct {
	ChatID    int64 `json:"chat_id"`
	MessageID int   `json:"message_id"`
}

func (b *Bot) DeleteMessage(chatID int64, messageID int) error {
	var resp APIResponse[bool]
	return b.doRequest("deleteMessage", deleteMessageRequest{
		ChatID:    chatID,
		MessageID: messageID,
	}, &resp)
}

type UpdateTask struct {
	cancel    context.CancelFunc
	messageID int
}

var (
	tasksMu sync.Mutex
	tasks   = map[int64]*UpdateTask{}
)

func stopAndDelete(bot *Bot, chatID int64) {
	tasksMu.Lock()
	task := tasks[chatID]
	if task != nil {
		delete(tasks, chatID)
	}
	tasksMu.Unlock()

	if task != nil {
		task.cancel()
		_ = bot.DeleteMessage(chatID, task.messageID)
	}
}

func startMonitoring(bot *Bot, chatID int64, messageID int, updateFn func() (string, error)) {
	ctx, cancel := context.WithCancel(context.Background())
	task := &UpdateTask{
		cancel:    cancel,
		messageID: messageID,
	}

	tasksMu.Lock()
	tasks[chatID] = task
	tasksMu.Unlock()

	go func() {
		defer func() {
			tasksMu.Lock()
			if tasks[chatID] == task {
				delete(tasks, chatID)
			}
			tasksMu.Unlock()
		}()

		ticker := time.NewTicker(updateInterval)
		defer ticker.Stop()
		deadline := time.Now().Add(maxUpdateDuration)

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				if time.Now().After(deadline) {
					return
				}
				text, err := updateFn()
				if err != nil {
					log.Printf("update error: %v", err)
					continue
				}
				if err := bot.EditMessage(chatID, messageID, text); err != nil {
					if shouldStopOnEditError(err) {
						return
					}
					log.Printf("edit error: %v", err)
					continue
				}
			}
		}
	}()
}

func shouldStopOnEditError(err error) bool {
	if err == nil {
		return false
	}
	msg := strings.ToLower(err.Error())
	return strings.Contains(msg, "message to edit not found") ||
		strings.Contains(msg, "message can't be edited") ||
		strings.Contains(msg, "message is too old")
}

func parseAllowedUsers(raw string) map[int64]bool {
	out := map[int64]bool{}
	for _, part := range strings.Split(raw, ",") {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		id, err := strconv.ParseInt(part, 10, 64)
		if err == nil {
			out[id] = true
		}
	}
	return out
}

func parseCommand(text string) string {
	text = strings.TrimSpace(text)
	if !strings.HasPrefix(text, "/") {
		return ""
	}
	fields := strings.Fields(text)
	if len(fields) == 0 {
		return ""
	}
	cmd := strings.TrimPrefix(fields[0], "/")
	if at := strings.Index(cmd, "@"); at >= 0 {
		cmd = cmd[:at]
	}
	return strings.ToLower(cmd)
}

func main() {
	token := strings.TrimSpace(os.Getenv("BOT_TOKEN"))
	if token == "" {
		log.Fatal("BOT_TOKEN is required")
	}
	allowed := parseAllowedUsers(os.Getenv("ALLOWED_USERS"))
	if len(allowed) == 0 {
		log.Fatal("ALLOWED_USERS is required")
	}

	bot := NewBot(token)
	go monitorReboot(bot, allowed)

	watchDirs := parseWatchDirs(os.Getenv("WATCH_DIRS"))
	if len(watchDirs) > 0 {
		go monitorDirs(bot, allowed, watchDirs)
	}
	watchUnits := parseWatchUnits(os.Getenv("WATCH_UNITS"))
	if len(watchUnits) == 0 {
		prefixes := parseWatchPrefixes(os.Getenv("WATCH_UNIT_PREFIXES"))
		if len(prefixes) > 0 {
			watchUnits = loadUnitsByPrefix(prefixes)
		}
	}
	if len(watchUnits) > 0 {
		go monitorUnits(bot, allowed, watchUnits)
	}

	offset := 0
	for {
		updates, err := bot.GetUpdates(offset)
		if err != nil {
			log.Printf("getUpdates error: %v", err)
			time.Sleep(3 * time.Second)
			continue
		}

		for _, upd := range updates {
			offset = upd.UpdateID + 1
			if upd.Message == nil || upd.Message.From == nil {
				continue
			}
			if !allowed[upd.Message.From.ID] {
				continue
			}
			cmd := parseCommand(upd.Message.Text)
			if cmd == "" {
				continue
			}

			chatID := upd.Message.Chat.ID
			switch cmd {
			case "status":
				stopAndDelete(bot, chatID)
				text, err := formatStatus()
				if err != nil {
					log.Printf("status error: %v", err)
					continue
				}
				msgID, err := bot.SendMessage(chatID, text)
				if err != nil {
					log.Printf("send status error: %v", err)
					continue
				}
				startMonitoring(bot, chatID, msgID, formatStatus)
			case "network":
				stopAndDelete(bot, chatID)
				text, err := formatNetwork()
				if err != nil {
					log.Printf("network error: %v", err)
					continue
				}
				msgID, err := bot.SendMessage(chatID, text)
				if err != nil {
					log.Printf("send network error: %v", err)
					continue
				}
				startMonitoring(bot, chatID, msgID, formatNetwork)
			case "process":
				stopAndDelete(bot, chatID)
				text, err := formatProcesses()
				if err != nil {
					log.Printf("process error: %v", err)
					continue
				}
				msgID, err := bot.SendMessage(chatID, text)
				if err != nil {
					log.Printf("send process error: %v", err)
					continue
				}
				startMonitoring(bot, chatID, msgID, formatProcesses)
			case "stop":
				stopAndDelete(bot, chatID)
			}
		}
	}
}

func monitorReboot(bot *Bot, allowed map[int64]bool) {
	lastBoot := readBootTime()
	first := true

	for {
		time.Sleep(rebootCheckSeconds * time.Second)
		current := readBootTime()
		if current.IsZero() {
			continue
		}
		if current != lastBoot {
			if !first {
				msg := "🔄 <b>Обнаружена перезагрузка сервера!</b>\n\n" +
					"⏱ Время перезагрузки: " + current.Format("2006-01-02 15:04:05")
				for userID := range allowed {
					_, _ = bot.SendMessage(userID, msg)
				}
			}
			lastBoot = current
		}
		first = false
	}
}

func parseWatchDirs(raw string) []string {
	var out []string
	for _, part := range strings.Split(raw, ",") {
		part = strings.TrimSpace(part)
		if part != "" {
			out = append(out, part)
		}
	}
	return out
}

func parseWatchUnits(raw string) []string {
	var out []string
	for _, part := range strings.Split(raw, ",") {
		part = strings.TrimSpace(part)
		if part != "" {
			out = append(out, part)
		}
	}
	return out
}

func parseWatchPrefixes(raw string) []string {
	if strings.TrimSpace(raw) == "" {
		return []string{"kab-", "tg_"}
	}
	var out []string
	for _, part := range strings.Split(raw, ",") {
		part = strings.TrimSpace(part)
		if part != "" {
			out = append(out, part)
		}
	}
	return out
}

func loadUnitsByPrefix(prefixes []string) []string {
	entries, err := os.ReadDir("/etc/systemd/system")
	if err != nil {
		return nil
	}
	seen := map[string]bool{}
	var out []string
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		name := entry.Name()
		if !strings.HasSuffix(name, ".service") {
			continue
		}
		for _, p := range prefixes {
			if strings.HasPrefix(name, p) {
				if !seen[name] {
					seen[name] = true
					out = append(out, name)
				}
				break
			}
		}
	}
	sort.Strings(out)
	return out
}

func monitorDirs(bot *Bot, allowed map[int64]bool, dirs []string) {
	prev := map[string]int{}
	for _, d := range dirs {
		prev[d] = -1
	}

	ticker := time.NewTicker(dirCheckSeconds * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		counts := countProcessesByDir(dirs)
		for _, d := range dirs {
			current := counts[d]
			last := prev[d]
			if last >= 0 {
				if last > 0 && current == 0 {
					msg := fmt.Sprintf("⚠️ <b>Нет процессов из каталога</b>\n\n<code>%s</code>", d)
					for userID := range allowed {
						_, _ = bot.SendMessage(userID, msg)
					}
				} else if last == 0 && current > 0 {
					msg := fmt.Sprintf("✅ <b>Процессы снова появились</b>\n\n<code>%s</code>\nКоличество: %d", d, current)
					for userID := range allowed {
						_, _ = bot.SendMessage(userID, msg)
					}
				}
			}
			prev[d] = current
		}
	}
}

func monitorUnits(bot *Bot, allowed map[int64]bool, units []string) {
	prev := map[string]string{}
	for _, u := range units {
		prev[u] = ""
	}

	ticker := time.NewTicker(unitCheckSeconds * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		for _, u := range units {
			status := systemdUnitStatus(u)
			last := prev[u]
			if last != "" && status != last {
				if status != "active" {
					msg := fmt.Sprintf("⚠️ <b>Unit не активен</b>\n\n<code>%s</code>\nСтатус: %s", u, status)
					for userID := range allowed {
						_, _ = bot.SendMessage(userID, msg)
					}
				} else {
					msg := fmt.Sprintf("✅ <b>Unit снова активен</b>\n\n<code>%s</code>", u)
					for userID := range allowed {
						_, _ = bot.SendMessage(userID, msg)
					}
				}
			}
			prev[u] = status
		}
	}
}

func systemdUnitStatus(unit string) string {
	out, err := exec.Command("systemctl", "is-active", unit).Output()
	if err != nil {
		// systemctl returns non-zero for inactive/failed/not-found
		if ee, ok := err.(*exec.ExitError); ok {
			text := strings.TrimSpace(string(ee.Stderr))
			if text != "" {
				return text
			}
		}
	}
	status := strings.TrimSpace(string(out))
	if status == "" {
		return "unknown"
	}
	return status
}

func readBootTime() time.Time {
	file, err := os.Open("/proc/stat")
	if err != nil {
		return time.Time{}
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "btime ") {
			parts := strings.Fields(line)
			if len(parts) >= 2 {
				sec, err := strconv.ParseInt(parts[1], 10, 64)
				if err == nil {
					return time.Unix(sec, 0)
				}
			}
		}
	}
	return time.Time{}
}

func formatStatus() (string, error) {
	cpuPercent, err := getCPUPercent()
	if err != nil {
		return "", err
	}
	memTotal, memAvail, err := getMemInfo()
	if err != nil {
		return "", err
	}
	swapTotal, swapFree, err := getSwapInfo()
	if err != nil {
		return "", err
	}
	disks, err := getDisks()
	if err != nil {
		return "", err
	}
	uptime, err := getUptime()
	if err != nil {
		return "", err
	}
	osName := getOSName()

	memUsed := memTotal - memAvail
	memPercent := float64(memUsed) / float64(memTotal) * 100
	swapUsed := swapTotal - swapFree
	swapPercent := 0.0
	if swapTotal > 0 {
		swapPercent = float64(swapUsed) / float64(swapTotal) * 100
	}

	var b strings.Builder
	b.WriteString("📊 <b>Статус сервера</b>\n\n")
	b.WriteString(fmt.Sprintf("🖥 <b>CPU:</b> %s\n", statusEmoji(cpuPercent)))
	b.WriteString(formatPercentage(cpuPercent))
	b.WriteString("\n\n")
	b.WriteString(fmt.Sprintf("💾 <b>RAM:</b> %s\n", statusEmoji(memPercent)))
	b.WriteString(formatPercentage(memPercent))
	b.WriteString("\n")
	b.WriteString(fmt.Sprintf("Использовано: %s / %s\n\n", formatBytes(memUsed), formatBytes(memTotal)))
	if swapTotal > 0 {
		b.WriteString(fmt.Sprintf("🧠 <b>SWAP:</b> %s\n", statusEmoji(swapPercent)))
		b.WriteString(formatPercentage(swapPercent))
		b.WriteString("\n")
		b.WriteString(fmt.Sprintf("Использовано: %s / %s\n\n", formatBytes(swapUsed), formatBytes(swapTotal)))
	}
	b.WriteString("💿 <b>Диски:</b>\n")
	for _, d := range disks {
		b.WriteString(fmt.Sprintf("%s <code>%s</code>\n", statusEmoji(d.UsedPercent), d.Mountpoint))
		b.WriteString("  " + formatPercentage(d.UsedPercent))
		b.WriteString("\n")
		b.WriteString(fmt.Sprintf("  %s свободно из %s\n", formatBytes(d.Free), formatBytes(d.Total)))
	}
	b.WriteString("\n")
	b.WriteString(fmt.Sprintf("⏱ <b>Uptime:</b> %s\n", uptime))
	b.WriteString(fmt.Sprintf("🖥 <b>OS:</b> %s", osName))

	return b.String(), nil
}

type DiskInfo struct {
	Mountpoint  string
	Total       uint64
	Free        uint64
	UsedPercent float64
}

func getDisks() ([]DiskInfo, error) {
	file, err := os.Open("/proc/mounts")
	if err != nil {
		return nil, err
	}
	defer file.Close()

	allowedFS := map[string]bool{
		"ext2": true, "ext3": true, "ext4": true, "xfs": true,
		"btrfs": true, "zfs": true, "vfat": true,
	}
	seen := map[string]bool{}
	var disks []DiskInfo

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		parts := strings.Fields(scanner.Text())
		if len(parts) < 3 {
			continue
		}
		mountpoint := parts[1]
		fstype := parts[2]
		if !allowedFS[fstype] {
			continue
		}
		if seen[mountpoint] {
			continue
		}
		seen[mountpoint] = true

		total, free, err := statFS(mountpoint)
		if err != nil {
			continue
		}
		if total == 0 {
			continue
		}
		used := total - free
		percent := float64(used) / float64(total) * 100

		disks = append(disks, DiskInfo{
			Mountpoint:  mountpoint,
			Total:       total,
			Free:        free,
			UsedPercent: percent,
		})
	}

	sort.Slice(disks, func(i, j int) bool {
		return disks[i].Mountpoint < disks[j].Mountpoint
	})
	return disks, nil
}

func statFS(path string) (total uint64, free uint64, err error) {
	var s syscall.Statfs_t
	if err := syscall.Statfs(path, &s); err != nil {
		return 0, 0, err
	}
	total = s.Blocks * uint64(s.Bsize)
	free = s.Bavail * uint64(s.Bsize)
	return total, free, nil
}

func getMemInfo() (total uint64, available uint64, err error) {
	file, err := os.Open("/proc/meminfo")
	if err != nil {
		return 0, 0, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "MemTotal:") {
			total = parseMeminfoValue(line)
		} else if strings.HasPrefix(line, "MemAvailable:") {
			available = parseMeminfoValue(line)
		}
	}
	if total == 0 || available == 0 {
		return 0, 0, fmt.Errorf("meminfo incomplete")
	}
	return total * 1024, available * 1024, nil
}

func getSwapInfo() (total uint64, free uint64, err error) {
	file, err := os.Open("/proc/meminfo")
	if err != nil {
		return 0, 0, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "SwapTotal:") {
			total = parseMeminfoValue(line)
		} else if strings.HasPrefix(line, "SwapFree:") {
			free = parseMeminfoValue(line)
		}
	}
	return total * 1024, free * 1024, nil
}

func parseMeminfoValue(line string) uint64 {
	fields := strings.Fields(line)
	if len(fields) < 2 {
		return 0
	}
	val, _ := strconv.ParseUint(fields[1], 10, 64)
	return val
}

func getCPUPercent() (float64, error) {
	idle1, total1, err := readCPUTimes()
	if err != nil {
		return 0, err
	}
	time.Sleep(150 * time.Millisecond)
	idle2, total2, err := readCPUTimes()
	if err != nil {
		return 0, err
	}

	deltaTotal := float64(total2 - total1)
	deltaIdle := float64(idle2 - idle1)
	if deltaTotal == 0 {
		return 0, nil
	}
	usage := (deltaTotal - deltaIdle) / deltaTotal * 100
	return usage, nil
}

func readCPUTimes() (idle uint64, total uint64, err error) {
	data, err := os.ReadFile("/proc/stat")
	if err != nil {
		return 0, 0, err
	}
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		if strings.HasPrefix(line, "cpu ") {
			fields := strings.Fields(line)
			if len(fields) < 5 {
				return 0, 0, fmt.Errorf("invalid cpu line")
			}
			var values []uint64
			for _, f := range fields[1:] {
				v, _ := strconv.ParseUint(f, 10, 64)
				values = append(values, v)
			}
			var sum uint64
			for _, v := range values {
				sum += v
			}
			idle = values[3]
			if len(values) > 4 {
				idle += values[4] // iowait
			}
			return idle, sum, nil
		}
	}
	return 0, 0, fmt.Errorf("cpu line not found")
}

func getUptime() (string, error) {
	data, err := os.ReadFile("/proc/uptime")
	if err != nil {
		return "", err
	}
	fields := strings.Fields(string(data))
	if len(fields) < 1 {
		return "", fmt.Errorf("uptime parse error")
	}
	secondsFloat, err := strconv.ParseFloat(fields[0], 64)
	if err != nil {
		return "", err
	}
	seconds := int64(secondsFloat)
	days := seconds / 86400
	hours := (seconds % 86400) / 3600
	mins := (seconds % 3600) / 60
	return fmt.Sprintf("%dд %dч %dм", days, hours, mins), nil
}

func getOSName() string {
	data, err := os.ReadFile("/etc/os-release")
	if err != nil {
		return runtimeOS()
	}
	for _, line := range strings.Split(string(data), "\n") {
		if strings.HasPrefix(line, "PRETTY_NAME=") {
			val := strings.TrimPrefix(line, "PRETTY_NAME=")
			return strings.Trim(val, "\"")
		}
	}
	return runtimeOS()
}

func runtimeOS() string {
	return runtime.GOOS
}

func formatNetwork() (string, error) {
	stats, err := readNetDev()
	if err != nil {
		return "", err
	}
	total := NetDevStats{}
	for _, st := range stats {
		total.RxBytes += st.RxBytes
		total.TxBytes += st.TxBytes
		total.RxPackets += st.RxPackets
		total.TxPackets += st.TxPackets
		total.RxErr += st.RxErr
		total.TxErr += st.TxErr
		total.RxDrop += st.RxDrop
		total.TxDrop += st.TxDrop
	}

	var b strings.Builder
	b.WriteString("🌐 <b>Сетевая статистика</b>\n\n")
	b.WriteString(fmt.Sprintf("📤 Отправлено: %s\n", formatBytes(total.TxBytes)))
	b.WriteString(fmt.Sprintf("📥 Получено: %s\n", formatBytes(total.RxBytes)))
	b.WriteString(fmt.Sprintf("📦 Пакетов отправлено: %d\n", total.TxPackets))
	b.WriteString(fmt.Sprintf("📦 Пакетов получено: %d\n", total.RxPackets))
	b.WriteString(fmt.Sprintf("❗ Ошибок: in %d / out %d\n", total.RxErr, total.TxErr))
	b.WriteString(fmt.Sprintf("🚫 Drops: in %d / out %d\n\n", total.RxDrop, total.TxDrop))

	b.WriteString("🧩 <b>Интерфейсы:</b>\n")
	names := make([]string, 0, len(stats))
	for name := range stats {
		names = append(names, name)
	}
	sort.Strings(names)

	for _, name := range names {
		st := stats[name]
		info := getInterfaceInfo(name)
		b.WriteString(fmt.Sprintf("\n<b>%s</b> (%s, %s, MTU %d)\n", name, info.State, info.Speed, info.MTU))
		b.WriteString(fmt.Sprintf("  ↗ %s | ↘ %s\n", formatBytes(st.TxBytes), formatBytes(st.RxBytes)))
		b.WriteString(fmt.Sprintf("  pkts ↗ %d | ↘ %d\n", st.TxPackets, st.RxPackets))
		if info.MAC != "" {
			b.WriteString(fmt.Sprintf("  MAC: %s\n", info.MAC))
		}
		if len(info.IPv4) > 0 {
			b.WriteString(fmt.Sprintf("  IPv4: %s\n", strings.Join(info.IPv4, ", ")))
		}
		if len(info.IPv6) > 0 {
			b.WriteString(fmt.Sprintf("  IPv6: %s\n", strings.Join(info.IPv6, ", ")))
		}
	}

	return b.String(), nil
}

type NetDevStats struct {
	RxBytes   uint64
	TxBytes   uint64
	RxPackets uint64
	TxPackets uint64
	RxErr     uint64
	TxErr     uint64
	RxDrop    uint64
	TxDrop    uint64
}

func readNetDev() (map[string]NetDevStats, error) {
	file, err := os.Open("/proc/net/dev")
	if err != nil {
		return nil, err
	}
	defer file.Close()

	stats := map[string]NetDevStats{}
	scanner := bufio.NewScanner(file)
	lineNo := 0
	for scanner.Scan() {
		lineNo++
		if lineNo <= 2 {
			continue
		}
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		parts := strings.Split(line, ":")
		if len(parts) != 2 {
			continue
		}
		iface := strings.TrimSpace(parts[0])
		fields := strings.Fields(parts[1])
		if len(fields) < 16 {
			continue
		}
		parse := func(i int) uint64 {
			v, _ := strconv.ParseUint(fields[i], 10, 64)
			return v
		}
		stats[iface] = NetDevStats{
			RxBytes:   parse(0),
			RxPackets: parse(1),
			RxErr:     parse(2),
			RxDrop:    parse(3),
			TxBytes:   parse(8),
			TxPackets: parse(9),
			TxErr:     parse(10),
			TxDrop:    parse(11),
		}
	}
	return stats, nil
}

type InterfaceInfo struct {
	State string
	Speed string
	MTU   int
	MAC   string
	IPv4  []string
	IPv6  []string
}

func getInterfaceInfo(name string) InterfaceInfo {
	info := InterfaceInfo{
		State: "unknown",
		Speed: "n/a",
	}
	iface, err := net.InterfaceByName(name)
	if err != nil {
		return info
	}
	info.MTU = iface.MTU
	if len(iface.HardwareAddr) > 0 {
		info.MAC = iface.HardwareAddr.String()
	}

	if state, err := os.ReadFile(filepath.Join("/sys/class/net", name, "operstate")); err == nil {
		info.State = strings.TrimSpace(string(state))
	}
	if speed, err := os.ReadFile(filepath.Join("/sys/class/net", name, "speed")); err == nil {
		info.Speed = strings.TrimSpace(string(speed)) + " Mbps"
	}

	addrs, err := iface.Addrs()
	if err == nil {
		for _, addr := range addrs {
			ip, _, err := net.ParseCIDR(addr.String())
			if err != nil || ip == nil {
				continue
			}
			if ip.To4() != nil {
				info.IPv4 = append(info.IPv4, ip.String())
			} else {
				info.IPv6 = append(info.IPv6, ip.String())
			}
		}
	}
	return info
}

type ProcInfo struct {
	PID   int
	Name  string
	RSSKB uint64
}

func formatProcesses() (string, error) {
	total, _, err := getMemInfo()
	if err != nil {
		return "", err
	}
	procs, err := getTopProcesses()
	if err != nil {
		return "", err
	}

	var b strings.Builder
	b.WriteString("📋 <b>Топ-10 самых тяжёлых процессов</b>\n\n")
	for i, p := range procs {
		percent := float64(p.RSSKB*1024) / float64(total) * 100
		b.WriteString(fmt.Sprintf("%d. <b>%s</b>\n", i+1, p.Name))
		b.WriteString(fmt.Sprintf("   PID: %d | RAM: %.1f%% (%s)\n", p.PID, percent, formatBytes(p.RSSKB*1024)))
	}
	return b.String(), nil
}

func getTopProcesses() ([]ProcInfo, error) {
	entries, err := os.ReadDir("/proc")
	if err != nil {
		return nil, err
	}

	var procs []ProcInfo
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		pid, err := strconv.Atoi(entry.Name())
		if err != nil {
			continue
		}
		info, err := readProcStatus(pid)
		if err != nil {
			continue
		}
		procs = append(procs, info)
	}

	sort.Slice(procs, func(i, j int) bool {
		return procs[i].RSSKB > procs[j].RSSKB
	})

	if len(procs) > 10 {
		procs = procs[:10]
	}
	return procs, nil
}

func countProcessesByDir(dirs []string) map[string]int {
	counts := map[string]int{}
	for _, d := range dirs {
		counts[d] = 0
	}

	entries, err := os.ReadDir("/proc")
	if err != nil {
		return counts
	}

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		pid, err := strconv.Atoi(entry.Name())
		if err != nil {
			continue
		}

		exePath, _ := os.Readlink(filepath.Join("/proc", strconv.Itoa(pid), "exe"))
		cmdline := readCmdline(pid)

		if exePath == "" && cmdline == "" {
			continue
		}

		for _, d := range dirs {
			if (exePath != "" && strings.Contains(exePath, d)) ||
				(cmdline != "" && strings.Contains(cmdline, d)) {
				counts[d]++
			}
		}
	}
	return counts
}

func readCmdline(pid int) string {
	data, err := os.ReadFile(filepath.Join("/proc", strconv.Itoa(pid), "cmdline"))
	if err != nil || len(data) == 0 {
		return ""
	}
	return strings.ReplaceAll(string(data), "\x00", " ")
}

func readProcStatus(pid int) (ProcInfo, error) {
	path := filepath.Join("/proc", strconv.Itoa(pid), "status")
	file, err := os.Open(path)
	if err != nil {
		return ProcInfo{}, err
	}
	defer file.Close()

	var name string
	var rssKB uint64

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "Name:") {
			fields := strings.Fields(line)
			if len(fields) >= 2 {
				name = fields[1]
			}
		} else if strings.HasPrefix(line, "VmRSS:") {
			fields := strings.Fields(line)
			if len(fields) >= 2 {
				rssKB, _ = strconv.ParseUint(fields[1], 10, 64)
			}
		}
	}

	if name == "" {
		return ProcInfo{}, fmt.Errorf("empty name")
	}
	return ProcInfo{PID: pid, Name: name, RSSKB: rssKB}, nil
}

func formatBytes(bytes uint64) string {
	units := []string{"B", "KB", "MB", "GB", "TB"}
	val := float64(bytes)
	unit := 0
	for val >= 1024 && unit < len(units)-1 {
		val /= 1024
		unit++
	}
	return fmt.Sprintf("%.1f %s", val, units[unit])
}

func formatPercentage(value float64) string {
	barLength := 10
	filled := int(float64(barLength) * value / 100)
	if filled < 0 {
		filled = 0
	}
	if filled > barLength {
		filled = barLength
	}
	bar := strings.Repeat("█", filled) + strings.Repeat("░", barLength-filled)
	return fmt.Sprintf("%s %.1f%%", bar, value)
}

func statusEmoji(value float64) string {
	if value < 50 {
		return "🟢"
	}
	if value < 80 {
		return "🟡"
	}
	return "🔴"
}

func trimMessage(text string) string {
	runes := []rune(text)
	if len(runes) <= telegramMaxRunes {
		return text
	}
	return string(runes[:telegramMaxRunes]) + "\n…"
}

