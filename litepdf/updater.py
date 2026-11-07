"""Tự cập nhật: tìm bản phát hành mới nhất trên GitHub, tải đúng bộ cài cho máy đang dùng rồi chạy cài đặt.

Bộ cài lấy từ trang phát hành của dự án (https://github.com/ngthhung-dev/pdf-editor-lite/releases):
  - Windows 64-bit:     PDF-Editor-Lite-<bản>-Setup.exe
  - macOS chip Apple:   PDF-Editor-Lite-<bản>-macOS-AppleSilicon.pkg
  - macOS chip Intel:   PDF-Editor-Lite-<bản>-macOS-Intel.pkg
  - Linux (Debian/Ubuntu/Mint 64-bit): pdf-editor-lite_<bản>_amd64.deb
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

REPO = "ngthhung-dev/pdf-editor-lite"
RELEASES_URL = f"https://github.com/{REPO}/releases"
API = f"https://api.github.com/repos/{REPO}/releases?per_page=15"
UA = "PDF-Editor-Lite-updater"
# tham số riêng của bộ cài Windows: cài xong thì tự mở lại app (bộ cài chạy ẩn sẽ bỏ qua bước "Mở PDF Editor Lite")
WIN_ARGS = "/SILENT /SP- /SUPPRESSMSGBOXES /NORESTART /LITEPDFRELAUNCH"


class UpdateError(Exception):
    """Lỗi khi tìm / tải bản cập nhật, câu báo đã viết sẵn cho người dùng."""


def parse_version(v: str) -> tuple[int, ...]:
    """'v1.0.24' -> (1, 0, 24). Chuỗi không phải số phiên bản -> ()."""
    m = re.match(r"^\s*v?(\d+(?:\.\d+)*)", v or "")
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def newer(a: str, b: str) -> bool:
    """Bản a mới hơn bản b?"""
    va, vb = parse_version(a), parse_version(b)
    n = max(len(va), len(vb))
    return bool(va) and va + (0,) * (n - len(va)) > vb + (0,) * (n - len(vb))


def platform_key(system: str | None = None, machine: str | None = None) -> str | None:
    """Loại bộ cài hợp với máy đang chạy: 'windows' | 'mac-arm' | 'mac-intel' | 'linux-deb' | None (không có bộ cài)."""
    system = system or sys.platform
    machine = (machine or platform.machine() or "").lower()
    if system.startswith("win"):
        return "windows" if machine in ("amd64", "x86_64", "arm64", "") else None
    if system == "darwin":
        if machine == "x86_64" and _rosetta():
            machine = "arm64"                   # app bản Intel chạy qua Rosetta trên máy chip Apple: cài bản chip Apple
        return "mac-arm" if machine == "arm64" else "mac-intel"
    if system.startswith("linux"):
        return "linux-deb" if machine in ("x86_64", "amd64") and shutil.which("dpkg") else None
    return None


def _rosetta() -> bool:
    try:
        out = subprocess.run(["sysctl", "-n", "sysctl.proc_translated"], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() == "1"
    except Exception:
        return False


def asset_matches(name: str, key: str) -> bool:
    n = name.lower()
    return {"windows": n.endswith("-setup.exe"),
            "mac-arm": n.endswith("-macos-applesilicon.pkg"),
            "mac-intel": n.endswith("-macos-intel.pkg"),
            "linux-deb": n.endswith("_amd64.deb")}.get(key, False)


PLATFORM_TEXT = {"windows": "Windows", "mac-arm": "macOS chip Apple", "mac-intel": "macOS chip Intel",
                 "linux-deb": "Linux (.deb)"}


def _context():
    try:                                         # bản đóng gói macOS / Linux: dùng kho chứng chỉ đi kèm cho chắc
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _open(url: str, timeout: float = 20, accept: str = "application/vnd.github+json"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=_context())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise UpdateError("GitHub tạm thời từ chối yêu cầu (hỏi quá nhiều lần). Thử lại sau ít phút.") from e
        raise UpdateError(f"GitHub trả về lỗi {e.code}.") from e
    except (urllib.error.URLError, OSError) as e:
        raise UpdateError("Không kết nối được tới GitHub. Kiểm tra mạng Internet rồi thử lại.\n\n"
                          f"Chi tiết: {getattr(e, 'reason', e)}") from e


def fetch_releases() -> list[dict]:
    with _open(API) as r:
        data = json.loads(r.read().decode("utf-8"))
    rels = [x for x in data if not x.get("draft") and not x.get("prerelease") and parse_version(x.get("tag_name", ""))]
    rels.sort(key=lambda x: parse_version(x["tag_name"]), reverse=True)
    return rels


def find_update(current: str, key: str | None = None, releases: list[dict] | None = None) -> dict:
    """Tìm bản mới hơn `current` có bộ cài cho máy này. Trả về:
      {"status": "latest" | "update" | "no_asset", "latest": bản mới nhất, "version", "tag", "page", "notes",
       "asset": {"name", "url", "size"}, "skipped": bản mới nhất nếu bản đó thiếu bộ cài cho máy này}"""
    key = key or platform_key()
    rels = fetch_releases() if releases is None else releases
    if not rels:
        raise UpdateError("Chưa tìm thấy bản phát hành nào trên GitHub.")
    latest = rels[0]["tag_name"].lstrip("v")
    out = {"latest": latest, "page": rels[0].get("html_url") or RELEASES_URL, "skipped": None}
    if not newer(latest, current):
        out["status"] = "latest"
        return out
    for rel in rels:
        ver = rel["tag_name"].lstrip("v")
        if not newer(ver, current):
            break
        asset = next((a for a in rel.get("assets", []) if key and asset_matches(a["name"], key)
                      and a.get("state", "uploaded") == "uploaded"), None)
        if asset:
            out.update(status="update", version=ver, tag=rel["tag_name"], page=rel.get("html_url") or RELEASES_URL,
                       notes=(rel.get("body") or "").strip(),
                       asset={"name": asset["name"], "url": asset["browser_download_url"], "size": int(asset.get("size") or 0)},
                       skipped=latest if ver != latest else None)
            return out
    out["status"] = "no_asset"                   # có bản mới nhưng chưa có bộ cài cho loại máy này
    return out


def download_dir() -> str:
    d = os.path.join(tempfile.gettempdir(), "PDFEditorLite-update")
    os.makedirs(d, exist_ok=True)
    return d


def download(asset: dict, progress=None, cancelled=None, dest_dir: str | None = None) -> str:
    """Tải bộ cài về thư mục tạm. progress(đã tải, tổng); cancelled() -> True thì dừng. Trả về đường dẫn file."""
    dest_dir = dest_dir or download_dir()
    name = os.path.basename(asset["name"])
    path = os.path.join(dest_dir, name)
    part = path + ".part"
    total = int(asset.get("size") or 0)
    if total and os.path.isfile(path) and os.path.getsize(path) == total:
        return path                              # đã tải đủ từ lần trước
    got = 0
    with _open(asset["url"], timeout=60, accept="application/octet-stream") as r, open(part, "wb") as f:
        total = total or int(r.headers.get("Content-Length") or 0)
        while True:
            if cancelled and cancelled():
                f.close()
                _remove(part)
                raise UpdateError("Đã huỷ tải bản cập nhật.")
            try:
                chunk = r.read(256 * 1024)
            except OSError as e:
                f.close()
                _remove(part)
                raise UpdateError(f"Mất kết nối khi đang tải bản cập nhật. Thử lại sau.\n\nChi tiết: {e}") from e
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if progress:
                progress(got, total)
    if total and got != total:
        _remove(part)
        raise UpdateError("File tải về không đủ dung lượng (mạng bị ngắt giữa chừng). Thử lại sau.")
    os.replace(part, path)
    return path


def _remove(p: str) -> None:
    try:
        os.remove(p)
    except OSError:
        pass


def install_command(path: str, key: str) -> list[str] | None:
    """Lệnh cài cho Linux (cần quyền quản trị): pkexec + apt-get / dpkg. None nếu máy không có pkexec."""
    if key != "linux-deb":
        return None
    pk = shutil.which("pkexec")
    if not pk:
        return None
    apt = shutil.which("apt-get")
    return [pk, apt, "install", "-y", path] if apt else [pk, shutil.which("dpkg") or "dpkg", "-i", path]


def launch_installer(path: str, key: str) -> None:
    """Chạy bộ cài Windows / macOS (tách khỏi app, app đóng lại ngay sau đó để bộ cài ghi đè được)."""
    if key == "windows":
        os.startfile(path, "open", WIN_ARGS)     # qua ShellExecute: Windows hỏi quyền quản trị (UAC) như khi bấm đúp
    elif key in ("mac-arm", "mac-intel"):
        subprocess.Popen(["open", path], start_new_session=True)     # mở trình cài đặt của macOS
    else:
        raise UpdateError("Máy này chưa hỗ trợ tự cài đặt.")
