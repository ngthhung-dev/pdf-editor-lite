"""Khởi động nhanh: chỉ nạp Qt, hiện khung chờ ngay, chuyển file cho cửa sổ đang mở (nếu có),
rồi mới nạp phần nặng (PyMuPDF, các hộp thoại...) và dựng cửa sổ chính."""
from __future__ import annotations

import os
import sys
import time

T0 = time.perf_counter()


def _process_age() -> float:
    """Số giây từ lúc hệ điều hành tạo tiến trình (gồm cả phần nạp thư viện trước khi Python chạy)."""
    try:
        if sys.platform.startswith("win"):
            import ctypes
            from ctypes import wintypes
            ft = [wintypes.FILETIME() for _ in range(4)]
            now = wintypes.FILETIME()
            k = ctypes.windll.kernel32
            k.GetCurrentProcess.restype = wintypes.HANDLE
            k.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
            k.GetProcessTimes(k.GetCurrentProcess(), *[ctypes.byref(f) for f in ft])
            k.GetSystemTimeAsFileTime(ctypes.byref(now))
            v = lambda f: (f.dwHighDateTime << 32) | f.dwLowDateTime
            return (v(now) - v(ft[0])) / 1e7
        if sys.platform.startswith("linux"):
            with open("/proc/self/stat") as f:
                start = int(f.read().rsplit(")", 1)[1].split()[19])
            with open("/proc/uptime") as f:
                up = float(f.read().split()[0])
            return up - start / os.sysconf("SC_CLK_TCK")
    except Exception:
        pass
    return time.perf_counter() - T0


MARKS: dict[str, float] = {}


def mark(name: str) -> None:
    MARKS[name] = round(_process_age(), 3)


def _instance_name() -> str:
    """Tên kênh nội bộ để các lần mở app của CÙNG một người dùng tìm thấy nhau."""
    import getpass
    import hashlib
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    return "PDFEditorLite-" + hashlib.md5(user.encode("utf-8", "ignore")).hexdigest()[:10]


def send_to_running(files: list[str]) -> bool:
    """App đang mở sẵn thì chuyển các file cho cửa sổ đó mở thành tab mới. Trả về True nếu đã chuyển xong."""
    import json
    from PySide6.QtNetwork import QLocalSocket
    sock = QLocalSocket()
    sock.connectToServer(_instance_name())
    if not sock.waitForConnected(400):
        return False
    if sys.platform.startswith("win"):      # cho phép cửa sổ đang mở tự nổi lên trước (Windows mặc định chặn việc này)
        try:
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(-1)
        except Exception:
            pass
    sock.write(json.dumps({"files": files}).encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(2000)
    # Đã nối được tức là có cửa sổ đang mở và nó sẽ nhận file. Chờ nó đóng kết nối (đã nhận xong) rồi thoát.
    if sock.state() != QLocalSocket.UnconnectedState:
        sock.waitForDisconnected(3000)
    return True


def _splash(files: list[str]):
    """Khung chờ nhỏ hiện ngay khi bấm mở, trong lúc nạp phần còn lại của app. Dùng ảnh vẽ sẵn: vẽ chữ lúc này
    buộc Qt dò hết phông trong máy (trên Windows mất hơn 1 giây), làm khung chờ hiện chậm đúng bằng chừng đó."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QPixmap
    from PySide6.QtWidgets import QLabel
    roots = [getattr(sys, "_MEIPASS", ""), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    pm = QPixmap()
    for r in roots:
        if r and pm.load(os.path.join(r, "assets", "splash.png")):
            break
    if pm.isNull():
        return None
    # Cửa sổ nhãn trơn thay cho QSplashScreen: QSplashScreen.show() có thể đứng chờ tới 1 giây cho cửa sổ "hiện ra".
    s = QLabel()
    s.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
    s.setPixmap(pm)
    s.resize(pm.size())
    scr = QGuiApplication.primaryScreen()
    if scr is not None:
        s.move(scr.availableGeometry().center() - s.rect().center())
    s.show()
    s.finish = lambda _w: s.close()
    return s


def main(argv: list[str]) -> int:
    mark("python")
    if len(argv) > 1 and argv[1] == "--selftest":
        from .app import selftest
        return selftest(argv[2] if len(argv) > 2 else None)
    from PySide6.QtWidgets import QApplication
    app = QApplication(argv)
    mark("qt")
    files = [os.path.abspath(a) for a in argv[1:] if not a.startswith("-") and os.path.exists(a)]
    lock = None
    try:        # đã có một cửa sổ PDF Editor Lite đang mở: giao file cho nó rồi thoát, không mở cửa sổ thứ hai
        from PySide6.QtCore import QDir, QLockFile
        # Cửa sổ chính giữ khoá suốt lúc chạy: lấy được khoá ngay nghĩa là chưa có cửa sổ nào, khỏi dò kênh (trên Windows
        # việc dò kênh khi không có ai nghe mất gần nửa giây). Nhiều file mở cùng lúc: chỉ MỘT tiến trình giữ được khoá
        # và thành cửa sổ chính, các tiến trình còn lại chờ nó khởi động xong rồi giao file cho nó.
        lock = QLockFile(os.path.join(QDir.tempPath(), _instance_name() + ".lock"))
        lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            end = time.time() + 25
            while time.time() < end:
                if send_to_running(files):
                    return 0
                if lock.tryLock(0):          # cửa sổ chính đã thoát giữa chừng: tiến trình này lên thay
                    break
                time.sleep(0.25)
    except Exception:
        pass
    mark("lock")
    splash = None
    try:
        splash = _splash(files)
        app.processEvents()
    except Exception:
        pass
    mark("splash")
    from .app import start
    mark("import")
    return start(app, files, lock, splash)
