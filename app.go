package main

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"tdlui/internal/tdl"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

type Config struct {
	Proxy        string `json:"proxy"`
	TDLPath      string `json:"tdl_path"`
	Namespace    string `json:"namespace"`
	DownloadPath string `json:"download_path"`
	Width        int    `json:"width"`
	Height       int    `json:"height"`
}

// App struct
type App struct {
	ctx    context.Context
	tdl    *tdl.Client
	config Config
}

const configPath = "config.json"
const defaultTDLPath = `D:\1TDL下载器\tdl.exe`

// NewApp creates a new App application struct
func NewApp() *App {
	a := &App{}
	a.loadConfig()

	path := a.config.TDLPath
	if path == "" {
		path = defaultTDLPath
	}
	// Defaults for window size
	if a.config.Width == 0 {
		a.config.Width = 1024
	}
	if a.config.Height == 0 {
		a.config.Height = 768
	}

	a.tdl = tdl.NewClient(path)
	if a.config.Proxy != "" {
		a.tdl.SetProxy(a.config.Proxy)
	}
	if a.config.Namespace != "" {
		a.tdl.SetNamespace(a.config.Namespace)
	}

	return a
}

func (a *App) loadConfig() {
	data, err := os.ReadFile(configPath)
	if err == nil {
		json.Unmarshal(data, &a.config)
	}
}

func (a *App) saveConfig() {
	data, _ := json.Marshal(a.config)
	os.WriteFile(configPath, data, 0644)
}

// startup is called when the app starts. The context is saved
// so we can call the runtime methods
func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
}

// shutdown is called when the app terminates
func (a *App) shutdown(ctx context.Context) {
	// Don't call WindowGetSize here as it may cause panic on Windows
}

// SaveWindowSize saves the current window dimensions via config
func (a *App) SaveWindowSize(width, height int) {
	a.config.Width = width
	a.config.Height = height
	a.saveConfig()
}

// GetVersion returns tdl version
func (a *App) GetVersion() (string, error) {
	return a.tdl.Version()
}

// SetProxy sets the proxy for tdl
func (a *App) SetProxy(proxy string) {
	a.config.Proxy = proxy
	a.tdl.SetProxy(proxy)
	a.saveConfig()
}

// GetProxy returns the current proxy
func (a *App) GetProxy() string {
	return a.config.Proxy
}

// SetTDLPath sets the path to tdl.exe
func (a *App) SetTDLPath(path string) {
	a.config.TDLPath = path
	a.tdl.SetPath(path)
	a.saveConfig()
}

// GetTDLPath returns current tdl path
func (a *App) GetTDLPath() string {
	if a.config.TDLPath == "" {
		return defaultTDLPath
	}
	return a.config.TDLPath
}

// SetNamespace sets the namespace for tdl
func (a *App) SetNamespace(ns string) {
	a.config.Namespace = ns
	a.tdl.SetNamespace(ns)
	a.saveConfig()
}

// GetNamespace returns current namespace
func (a *App) GetNamespace() string {
	return a.config.Namespace
}

// SetDownloadPath sets the default download directory
func (a *App) SetDownloadPath(path string) {
	a.config.DownloadPath = path
	a.saveConfig()
}

// GetDownloadPath returns current download path
func (a *App) GetDownloadPath() string {
	return a.config.DownloadPath
}

// SelectTDLFile opens a file selection dialog for tdl.exe
func (a *App) SelectTDLFile() (string, error) {
	return runtime.OpenFileDialog(a.ctx, runtime.OpenDialogOptions{
		Title: "选择 tdl.exe",
		Filters: []runtime.FileFilter{
			{DisplayName: "可执行文件 (*.exe)", Pattern: "*.exe"},
		},
	})
}

// SelectDownloadDir opens a directory selection dialog
func (a *App) SelectDownloadDir() (string, error) {
	return runtime.OpenDirectoryDialog(a.ctx, runtime.OpenDialogOptions{
		Title: "选择默认下载目录",
	})
}

// Download starts a download task
func (a *App) Download(url string, threads int) {
	logChan := make(chan string)

	go func() {
		for log := range logChan {
			runtime.EventsEmit(a.ctx, "tdl:log", log)
		}
	}()

	go func() {
		defer close(logChan)
		err := a.tdl.Download(a.ctx, url, a.config.DownloadPath, threads, logChan)
		if err != nil {
			runtime.EventsEmit(a.ctx, "tdl:error", err.Error())
		} else {
			runtime.EventsEmit(a.ctx, "tdl:success", "下载完成")
		}
	}()
}

// Upload starts an upload task
func (a *App) Upload(path string, chat string, threads int, remove bool, asPhoto bool) {
	logChan := make(chan string)

	go func() {
		for log := range logChan {
			runtime.EventsEmit(a.ctx, "tdl:log", log)
		}
	}()

	go func() {
		defer close(logChan)
		err := a.tdl.Upload(a.ctx, path, chat, threads, remove, asPhoto, logChan)
		if err != nil {
			runtime.EventsEmit(a.ctx, "tdl:error", err.Error())
		} else {
			runtime.EventsEmit(a.ctx, "tdl:success", "上传完成")
		}
	}()
}

// SelectFile opens a file selection dialog
func (a *App) SelectFile() (string, error) {
	return runtime.OpenFileDialog(a.ctx, runtime.OpenDialogOptions{
		Title: "选择上传文件",
	})
}

// SelectFolder opens a folder selection dialog
func (a *App) SelectFolder() (string, error) {
	return runtime.OpenDirectoryDialog(a.ctx, runtime.OpenDialogOptions{
		Title: "选择上传目录",
	})
}

// SelectFolderByFile allows user to pick a file to select its parent folder
func (a *App) SelectFolderByFile() (string, error) {
	path, err := runtime.OpenFileDialog(a.ctx, runtime.OpenDialogOptions{
		Title: "进入目录并选择任一文件以确定目录",
	})
	if err != nil || path == "" {
		return "", err
	}
	return filepath.Dir(path), nil
}

// SelectTextFile opens a file selection dialog for txt files
func (a *App) SelectTextFile() (string, error) {
	return runtime.OpenFileDialog(a.ctx, runtime.OpenDialogOptions{
		Title: "选择下载链接文件 (TXT)",
		Filters: []runtime.FileFilter{
			{DisplayName: "文本文件 (*.txt)", Pattern: "*.txt"},
		},
	})
}

// ReadTextFile reads the content of a file
func (a *App) ReadTextFile(path string) (string, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return string(content), nil
}
