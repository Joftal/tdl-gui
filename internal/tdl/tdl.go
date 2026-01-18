package tdl

import (
	"context"
	"fmt"
	"io"
	"os/exec"
	"regexp"
	"strings"
	"sync"
	"time"
)

type Client struct {
	mu        sync.RWMutex
	Path      string
	Proxy     string
	Namespace string
}

func NewClient(path string) *Client {
	return &Client{Path: path}
}

func (c *Client) SetProxy(proxy string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.Proxy = proxy
}

func (c *Client) SetPath(path string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.Path = path
}

func (c *Client) SetNamespace(ns string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.Namespace = ns
}

func (c *Client) getSettings() (string, string, string) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.Path, c.Proxy, c.Namespace
}

func (c *Client) Version() (string, error) {
	path, proxy, _ := c.getSettings()
	if path == "" {
		return "", fmt.Errorf("tdl path not set")
	}
	args := []string{"version"}
	if proxy != "" {
		args = append([]string{"--proxy", proxy}, args...)
	}

	cmd := exec.Command(c.Path, args...)
	setHideWindow(cmd)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

// Strip ANSI escape codes
var ansiRegex = regexp.MustCompile(`\x1b\[[0-9;]*[a-zA-Z]`)

func stripAnsi(str string) string {
	return ansiRegex.ReplaceAllString(str, "")
}

// Helper to filter and format the log line
func formatLogLine(line string) (string, bool) {
	// Filter out debug info
	if strings.Contains(line, "CPU:") || strings.Contains(line, "Goroutines:") {
		return "", false
	}
	// Filter out pure progress bar lines (that don't have filename info)
	// Usually these start with [####] and don't contain the detailed stats often
	// BUT, based on the screenshot, we want the line that HAS the filename.
	// The filename line looks like: "Name... 99.1% [###] [Stats...]"

	// Check for "done!"
	if strings.Contains(line, "done!") {
		return "LOG:✅ " + line, true
	}

	// Check for Error
	if strings.Contains(strings.ToLower(line), "error") || strings.Contains(strings.ToLower(line), "panic") {
		return "LOG:❌ " + line, true
	}

	// Heuristic for the MAIN progress line:
	// It should contain the filename (we can't easily guess that)
	// OR it should contain typical stats like "MB" "KB/s" and "%"
	// The screenshot shows TWO types of progress lines:
	// 1. "Filename... 99.1% [####] [Stats]"  <-- We want this one
	// 2. "[###############] [Time; Speed]"   <-- We want to ignore this one usually, as it lacks context

	// We want lines that have a "%" percentage indicator.
	if strings.Contains(line, "%") {
		// Clean up the line for better display?
		// For now, let's just pass it through as a PROGRESS update.
		return "PROG:" + line, true
	}

	// Explicitly ignore lines that start with [ and correspond to the pure bar
	if strings.TrimSpace(line) != "" && strings.HasPrefix(strings.TrimSpace(line), "[") && strings.Contains(line, "]") {
		return "", false
	}

	return "", false
}

// execute handles running a command and piping its output to logChan
func (c *Client) execute(ctx context.Context, args []string, logChan chan<- string) error {
	path, proxy, namespace := c.getSettings()

	if path == "" {
		return fmt.Errorf("tdl path not set")
	}
	finalArgs := []string{}

	// Prepend global flags
	if namespace != "" {
		finalArgs = append(finalArgs, "--ns", namespace)
	}
	if proxy != "" {
		finalArgs = append(finalArgs, "--proxy", proxy)
	}

	finalArgs = append(finalArgs, args...)

	cmd := exec.CommandContext(ctx, path, finalArgs...)
	setHideWindow(cmd)

	stdout, _ := cmd.StdoutPipe()
	stderr, _ := cmd.StderrPipe()

	if err := cmd.Start(); err != nil {
		return err
	}

	done := make(chan bool)

	// Custom reader that handles \r and \n manually
	readAndSend := func(r io.Reader) {
		buf := make([]byte, 1024)
		var lineBuffer []byte
		var lastTime time.Time

		processBuffer := func() {
			if len(lineBuffer) > 0 {
				cleanText := string(lineBuffer)
				cleanText = stripAnsi(cleanText)
				cleanText = strings.TrimSpace(cleanText)

				formatted, ok := formatLogLine(cleanText)
				if ok {
					// Throttle progress updates a bit
					if strings.HasPrefix(formatted, "PROG:") {
						if time.Since(lastTime) > 100*time.Millisecond {
							logChan <- formatted
							lastTime = time.Now()
						}
					} else {
						logChan <- formatted
					}
				}
				lineBuffer = lineBuffer[:0]
			}
		}

		for {
			n, err := r.Read(buf)
			if n > 0 {
				chunk := buf[:n]
				for _, b := range chunk {
					if b == '\r' || b == '\n' {
						processBuffer()
					} else {
						lineBuffer = append(lineBuffer, b)
					}
				}
			}
			if err != nil {
				processBuffer() // Process remaining
				break
			}
		}
		done <- true
	}

	go readAndSend(stdout)
	go readAndSend(stderr)

	err := cmd.Wait()
	<-done
	<-done
	return err
}

func (c *Client) Download(ctx context.Context, url string, dir string, threads int, logChan chan<- string) error {
	args := []string{"download", "-u", url, "--threads", fmt.Sprintf("%d", threads)}
	if dir != "" {
		args = append(args, "-d", dir)
	}
	return c.execute(ctx, args, logChan)
}

func (c *Client) Upload(ctx context.Context, path string, chat string, threads int, remove bool, asPhoto bool, logChan chan<- string) error {
	args := []string{"upload", "-p", path, "--threads", fmt.Sprintf("%d", threads)}
	if chat != "" {
		args = append(args, "-c", chat)
	}
	if remove {
		args = append(args, "--rm")
	}
	if asPhoto {
		args = append(args, "--photo")
	}
	return c.execute(ctx, args, logChan)
}
