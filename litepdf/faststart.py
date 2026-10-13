"""Khởi động nhanh: chạy sẵn PDF Editor Lite (ẩn, có biểu tượng ở khay hệ thống) khi đăng nhập máy.
Lần mở app hoặc nhấp đúp file PDF sau đó chỉ việc hiện cửa sổ đã dựng sẵn, không phải nạp lại thư viện và phông chữ."""
from __future__ import annotations

import os
import sys

from . import tools

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_NAME = "PDFEditorLite"


def command() -> list[str]:
    if tools.FROZEN:
        return [sys.executable, "--background"]
    main = os.path.join(tools.app_dir(), "main.py")
    exe = sys.executable.replace("python.exe", "pythonw.exe") if sys.platform.startswith("win") else sys.executable
    return [exe, main, "--background"]


def _linux_file() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "autostart", "pdf-editor-lite.desktop")


def _mac_file() -> str:
    return os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents", "dev.ngthhung.pdfeditorlite.plist")


def is_enabled() -> bool:
    try:
        if sys.platform.startswith("win"):
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
                v, _ = winreg.QueryValueEx(k, _NAME)
                return bool(v)
        if sys.platform == "darwin":
            return os.path.isfile(_mac_file())
        return os.path.isfile(_linux_file())
    except OSError:
        return False


def set_enabled(on: bool) -> None:
    cmd = command()
    if sys.platform.startswith("win"):
        import subprocess
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            if on:
                winreg.SetValueEx(k, _NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(cmd))
            else:
                try:
                    winreg.DeleteValue(k, _NAME)
                except FileNotFoundError:
                    pass
        return
    path = _mac_file() if sys.platform == "darwin" else _linux_file()
    if not on:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if sys.platform == "darwin":
        from xml.sax.saxutils import escape
        args = "".join(f"<string>{escape(a)}</string>" for a in cmd)
        text = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict>'
                '<key>Label</key><string>dev.ngthhung.pdfeditorlite</string>'
                f'<key>ProgramArguments</key><array>{args}</array><key>RunAtLoad</key><true/></dict></plist>\n')
    else:
        import shlex
        text = ("[Desktop Entry]\nType=Application\nName=PDF Editor Lite (khởi động nhanh)\n"
                f"Exec={' '.join(shlex.quote(a) for a in cmd)}\nIcon=pdf-editor-lite\nX-GNOME-Autostart-enabled=true\n"
                "NoDisplay=true\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
