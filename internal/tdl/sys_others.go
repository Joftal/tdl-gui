//go:build !windows
// +build !windows

package tdl

import "os/exec"

func setHideWindow(cmd *exec.Cmd) {}
