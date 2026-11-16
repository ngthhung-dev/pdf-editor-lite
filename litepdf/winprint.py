"""In trên Windows theo đúng cách của Windows (GDI), không qua bộ in của Qt.

Vì sao: Qt sửa thẳng các ô công khai của cấu hình máy in (DEVMODE) mà không nhờ driver cập nhật phần cài đặt riêng
của driver. Hệ quả đã gặp:
  - Zebra ZD220 khổ giấy tự đặt 70 × 100 mm: driver nhận khổ ~1 × 6 mm, in ra nhãn trắng;
  - Xerox WorkCentre 5335 mặc định in hai mặt: chọn "In một mặt" nhưng phiếu lệnh của Xerox vẫn ghi hai mặt.
Ở đây cấu hình được hợp nhất bằng DocumentProperties(DM_IN_BUFFER | DM_OUT_BUFFER) như mọi phần mềm Windows, nên
driver tự đồng bộ phần riêng (vd. <sides>one-sided</sides> của Xerox) và giữ nguyên khổ giấy tự đặt.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

DM_ORIENTATION, DM_PAPERSIZE, DM_COPIES, DM_COLOR, DM_DUPLEX, DM_COLLATE = 0x1, 0x2, 0x100, 0x800, 0x1000, 0x8000
DM_OUT_BUFFER, DM_IN_BUFFER = 2, 8
DMDUP = {"none": 1, "long": 2, "short": 3}       # DMDUP_SIMPLEX / VERTICAL (cạnh dài) / HORIZONTAL (cạnh ngắn)
DMCOLOR_MONOCHROME, DMCOLOR_COLOR = 1, 2
HORZRES, VERTRES, LOGPIXELSX, LOGPIXELSY = 8, 10, 88, 90
PHYSICALWIDTH, PHYSICALHEIGHT = 110, 111
SRCCOPY, DIB_RGB_COLORS, HALFTONE = 0x00CC0020, 0, 4
# vị trí các ô trong DEVMODEW
OFF_SIZE, OFF_EXTRA, OFF_FIELDS = 68, 70, 72
OFF_ORIENT, OFF_PAPER, OFF_COPIES, OFF_COLOR, OFF_DUPLEX, OFF_COLLATE = 76, 78, 86, 92, 94, 100


class PrintError(Exception):
    pass


class DOCINFOW(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_int), ("lpszDocName", wintypes.LPCWSTR), ("lpszOutput", wintypes.LPCWSTR),
                ("lpszDatatype", wintypes.LPCWSTR), ("fwType", wintypes.DWORD)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


def _api():
    ws = ctypes.WinDLL("winspool.drv", use_last_error=True)
    gdi = ctypes.WinDLL("gdi32", use_last_error=True)
    ws.OpenPrinterW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
    ws.ClosePrinter.argtypes = [wintypes.HANDLE]
    ws.DocumentPropertiesW.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.LPCWSTR, ctypes.c_void_p,
                                       ctypes.c_void_p, wintypes.DWORD]
    ws.DocumentPropertiesW.restype = ctypes.c_long
    gdi.CreateDCW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p]
    gdi.CreateDCW.restype = wintypes.HDC
    gdi.DeleteDC.argtypes = [wintypes.HDC]
    gdi.StartDocW.argtypes = [wintypes.HDC, ctypes.POINTER(DOCINFOW)]
    for f in ("StartPage", "EndPage", "EndDoc", "AbortDoc"):
        getattr(gdi, f).argtypes = [wintypes.HDC]
    gdi.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
    gdi.SetStretchBltMode.argtypes = [wintypes.HDC, ctypes.c_int]
    gdi.SetBrushOrgEx.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
    gdi.StretchDIBits.argtypes = [wintypes.HDC] + [ctypes.c_int] * 8 + [ctypes.c_void_p, ctypes.c_void_p,
                                                                        wintypes.UINT, wintypes.DWORD]
    return ws, gdi


def _u16(buf, off):
    return int.from_bytes(bytes(buf[off:off + 2]), "little", signed=True)


def _set16(buf, off, v):
    buf[off:off + 2] = int(v).to_bytes(2, "little", signed=True)


def job_devmode(printer: str, duplex: str = "none", gray: bool | None = None, paper_id: int = 0):
    """Cấu hình in cho một lệnh in: lấy cấu hình mặc định của máy in rồi nhờ driver hợp nhất các thay đổi
    (một / hai mặt, đen trắng, khổ giấy chuẩn nếu người dùng chọn). Trả về bộ đệm DEVMODE đã hợp nhất."""
    ws, _gdi = _api()
    h = wintypes.HANDLE()
    if not ws.OpenPrinterW(printer, ctypes.byref(h), None):
        raise PrintError(f"Không mở được máy in “{printer}”.")
    try:
        n = ws.DocumentPropertiesW(None, h, printer, None, None, 0)
        if n <= 0:
            raise PrintError("Không đọc được cấu hình của máy in.")
        dm = ctypes.create_string_buffer(n)
        if ws.DocumentPropertiesW(None, h, printer, dm, None, DM_OUT_BUFFER) < 0:
            raise PrintError("Không đọc được cấu hình của máy in.")
        fields = int.from_bytes(dm[OFF_FIELDS:OFF_FIELDS + 4], "little")
        _set16(dm, OFF_DUPLEX, DMDUP[duplex])
        _set16(dm, OFF_COPIES, 1)                 # số bản app tự gửi lặp (giữ đúng thứ tự xếp bộ, cặp mặt in hai mặt)
        fields |= DM_DUPLEX | DM_COPIES
        if gray is not None:
            _set16(dm, OFF_COLOR, DMCOLOR_MONOCHROME if gray else DMCOLOR_COLOR)
            fields |= DM_COLOR
        if paper_id > 0:                          # khổ giấy chuẩn người dùng chọn (A4, A5…); khổ tự đặt giữ như máy in
            _set16(dm, OFF_PAPER, paper_id)
            fields |= DM_PAPERSIZE
        dm[OFF_FIELDS:OFF_FIELDS + 4] = fields.to_bytes(4, "little")
        out = ctypes.create_string_buffer(n)
        if ws.DocumentPropertiesW(None, h, printer, out, dm, DM_IN_BUFFER | DM_OUT_BUFFER) < 0:
            raise PrintError("Máy in không nhận cấu hình in.")
        return out
    finally:
        ws.ClosePrinter(h)


def devmode_info(dm) -> dict:
    return {"paper": _u16(dm, OFF_PAPER), "duplex": _u16(dm, OFF_DUPLEX), "copies": _u16(dm, OFF_COPIES),
            "color": _u16(dm, OFF_COLOR), "orientation": _u16(dm, OFF_ORIENT)}


class GdiJob:
    """Một lệnh in GDI: begin() → mỗi mặt: page_size() / draw(QImage) → end()."""

    def __init__(self, printer: str, title: str, devmode, output: str | None = None):
        self.ws, self.gdi = _api()
        self.printer, self.title, self.devmode, self.output = printer, title, devmode, output
        self.hdc = None
        self.started = False

    def begin(self):
        self.hdc = self.gdi.CreateDCW(None, self.printer, None, self.devmode)
        if not self.hdc:
            raise PrintError("Không kết nối được máy in. Kiểm tra máy in đã bật và sẵn sàng chưa.")
        di = DOCINFOW(ctypes.sizeof(DOCINFOW), self.title or "PDF Editor Lite", self.output, None, 0)
        if self.gdi.StartDocW(self.hdc, ctypes.byref(di)) <= 0:
            self.gdi.DeleteDC(self.hdc)
            self.hdc = None
            raise PrintError("Máy in không nhận lệnh in.")
        self.started = True

    def caps(self) -> tuple[int, int, int, int]:
        """(rộng, cao) vùng in được tính bằng điểm thiết bị, (dpi ngang, dpi dọc)."""
        g = self.gdi
        return (g.GetDeviceCaps(self.hdc, HORZRES), g.GetDeviceCaps(self.hdc, VERTRES),
                g.GetDeviceCaps(self.hdc, LOGPIXELSX), g.GetDeviceCaps(self.hdc, LOGPIXELSY))

    def page(self, img) -> None:
        """In một mặt: ảnh QImage (RGB32) được kéo phủ đúng vùng in được của tờ giấy."""
        from PySide6.QtGui import QImage
        if img.format() != QImage.Format_RGB32:
            img = img.convertToFormat(QImage.Format_RGB32)
        w, h, _dx, _dy = self.caps()
        if self.gdi.StartPage(self.hdc) <= 0:
            raise PrintError("Máy in không nhận trang in.")
        bih = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), img.width(), -img.height(), 1, 32, 0, 0, 0, 0, 0, 0)
        bits = img.constBits()
        buf = (ctypes.c_char * img.sizeInBytes()).from_buffer_copy(bytes(bits))
        self.gdi.SetStretchBltMode(self.hdc, HALFTONE)
        self.gdi.SetBrushOrgEx(self.hdc, 0, 0, None)
        if self.gdi.StretchDIBits(self.hdc, 0, 0, w, h, 0, 0, img.width(), img.height(), buf, ctypes.byref(bih),
                                  DIB_RGB_COLORS, SRCCOPY) == 0:
            raise PrintError("Không gửi được hình trang in tới máy in.")
        self.gdi.EndPage(self.hdc)

    def end(self, ok: bool = True) -> None:
        if self.hdc:
            if self.started:
                (self.gdi.EndDoc if ok else self.gdi.AbortDoc)(self.hdc)
            self.gdi.DeleteDC(self.hdc)
            self.hdc = None
