"""Hộp thoại in có tuỳ chọn và xem trước."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pymupdf
from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter, QPen, QPixmap
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrinterInfo
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressDialog, QPushButton,
                               QSpinBox, QVBoxLayout)

from . import tools

PDF_PRINTER = "\x00pdf"
PAPERS = [("", "Theo mặc định của máy in"), ("A4", "A4 (210 × 297 mm)"), ("A3", "A3 (297 × 420 mm)"),
          ("A5", "A5 (148 × 210 mm)"), ("B5", "B5 (176 × 250 mm)"), ("Letter", "Letter (216 × 279 mm)"),
          ("Legal", "Legal (216 × 356 mm)")]
MAX_PIXELS = 40_000_000


@dataclass
class PrintOptions:
    pages: list[int] = field(default_factory=list)  # thứ tự trang sẽ in (chỉ số từ 0)
    copies: int = 1
    collate: bool = True
    paper: str = ""
    orientation: str = "auto"      # auto | portrait | landscape
    scale: str = "fit"             # fit | actual | shrink | custom
    percent: float = 100.0
    nup: int = 1
    borders: bool = False
    gray: bool = False
    annots: bool = True
    duplex: str = "none"           # none | long | short
    center: bool = True
    booklet: bool = False
    booklet_side: str = "both"     # both | front | back
    binding: str = "left"          # left | right
    reverse_sheets: bool = False


def grid(n: int, landscape: bool) -> tuple[int, int]:
    """(cột, hàng) cho n trang trên một tờ."""
    if n == 1:
        return 1, 1
    if n == 2:
        return (2, 1) if landscape else (1, 2)
    if n == 6:
        return (3, 2) if landscape else (2, 3)
    k = int(math.isqrt(n))
    return k, k


def sheets(opts: PrintOptions) -> list[list]:
    """Danh sách các mặt giấy; mỗi mặt là danh sách chỉ số trang (None = ô trắng)."""
    if opts.booklet:
        return booklet_sides(opts)
    n = max(1, opts.nup)
    return [opts.pages[i:i + n] for i in range(0, len(opts.pages), n)]


def booklet_sides(opts: PrintOptions) -> list[list]:
    """Xếp trang kiểu sách gập đôi, ghim giữa: tờ ngoài cùng mang trang đầu và trang cuối."""
    pg: list = list(opts.pages)
    if not pg:
        return []
    while len(pg) % 4:
        pg.append(None)
    n = len(pg)
    out = []
    for i in range(n // 4):
        front = [pg[n - 1 - 2 * i], pg[2 * i]]
        back = [pg[2 * i + 1], pg[n - 2 - 2 * i]]
        if opts.binding == "right":
            front.reverse()
            back.reverse()
        if opts.booklet_side in ("both", "front"):
            out.append(front)
        if opts.booklet_side in ("both", "back"):
            out.append(back)
    if opts.reverse_sheets:
        out.reverse()
    return out


def _first(pages: list):
    return next((x for x in pages if x is not None), None)


def sheet_landscape(doc, pages: list[int], opts: PrintOptions) -> bool:
    first = _first(pages)
    if first is None:
        return opts.booklet
    if opts.booklet:  # hai trang dọc nằm cạnh nhau trên tờ ngang
        r = doc[first].rect
        return r.height >= r.width
    if opts.orientation == "portrait":
        return False
    if opts.orientation == "landscape":
        return True
    r = doc[first].rect
    page_land = r.width > r.height
    if opts.nup in (2, 6):  # 2 hoặc 6 trang dọc xếp đẹp nhất trên tờ ngang
        return not page_land
    return page_land


def draw_sheet(p: QPainter, w: float, h: float, upp: float, doc, pages: list, opts: PrintOptions,
               max_dpi: float = 300.0, crisp: bool = False) -> None:
    """Vẽ một mặt giấy vào vùng (0,0,w,h). upp = số đơn vị vẽ trên mỗi point PDF.
    crisp=True (xem trước): kết xuất đúng số điểm ảnh sẽ hiển thị và vẽ 1:1 để chữ không bị nhoè."""
    multi = opts.booklet or opts.nup > 1
    if opts.booklet:
        cols, rows = (2, 1) if w > h else (1, 2)
        gap = 0.0
    else:
        cols, rows = grid(opts.nup, w > h)
        gap = 0 if opts.nup == 1 else 8 * upp
    cw = (w - gap * (cols - 1)) / cols
    ch = (h - gap * (rows - 1)) / rows
    for k, pno in enumerate(pages):
        if pno is None:
            continue
        page = doc[pno]
        pw, ph = page.rect.width * upp, page.rect.height * upp
        fit = min(cw / pw, ch / ph)
        if multi or opts.scale == "fit":
            s = fit
        elif opts.scale == "actual":
            s = 1.0
        elif opts.scale == "shrink":
            s = min(1.0, fit)
        else:
            s = max(0.05, opts.percent / 100.0)
        tw, th = pw * s, ph * s
        cx = (k % cols) * (cw + gap)
        cy = (k // cols) * (ch + gap)
        x = cx + ((cw - tw) / 2 if opts.center or multi else 0)
        y = cy + ((ch - th) / 2 if opts.center or multi else 0)
        exact = s * upp
        z = min(exact, max_dpi / 72.0, math.sqrt(MAX_PIXELS / max(1.0, page.rect.width * page.rect.height)))
        pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False, annots=opts.annots,
                              colorspace=pymupdf.csGRAY if opts.gray else pymupdf.csRGB)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride,
                     QImage.Format_Grayscale8 if opts.gray else QImage.Format_RGB888)
        p.save()
        p.setClipRect(QRectF(cx, cy, cw, ch))
        if crisp and z == exact:
            p.setRenderHint(QPainter.SmoothPixmapTransform, False)
            p.drawImage(QRectF(round(x), round(y), img.width(), img.height()), img)
        else:
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
            p.drawImage(QRectF(x, y, tw, th), img)
        if opts.borders:
            p.setPen(QPen(QColor("#808080"), max(1.0, 0.5 * upp)))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(x, y, tw, th))
        p.restore()


def apply_options(printer: QPrinter, opts: PrintOptions) -> None:
    if opts.paper:
        printer.setPageSize(QPageSize(getattr(QPageSize, opts.paper)))
    printer.setCopyCount(max(1, opts.copies))
    printer.setCollateCopies(opts.collate)
    printer.setColorMode(QPrinter.GrayScale if opts.gray else QPrinter.Color)
    printer.setDuplex({"none": QPrinter.DuplexNone, "long": QPrinter.DuplexLongSide,
                       "short": QPrinter.DuplexShortSide}[opts.duplex])


def run_print(printer: QPrinter, doc, opts: PrintOptions, parent=None) -> int:
    """In thật. Trả về số tờ đã gửi."""
    apply_options(printer, opts)
    sh = sheets(opts)
    if not sh:
        return 0
    prog = QProgressDialog("Đang gửi lệnh in…", "Dừng", 0, len(sh), parent)
    prog.setWindowModality(Qt.WindowModal)
    prog.setMinimumDuration(400)
    painter = None
    done = 0
    try:
        for k, pages in enumerate(sh):
            printer.setPageOrientation(QPageLayout.Landscape if sheet_landscape(doc, pages, opts)
                                       else QPageLayout.Portrait)
            if painter is None:
                painter = QPainter()
                if not painter.begin(printer):
                    raise tools.PdfError("Không kết nối được máy in. Kiểm tra máy in đã bật và sẵn sàng chưa.")
            else:
                printer.newPage()
            vp = painter.viewport()
            draw_sheet(painter, vp.width(), vp.height(), printer.resolution() / 72.0, doc, pages, opts)
            done += 1
            prog.setValue(k + 1)
            QApplication.processEvents()
            if prog.wasCanceled():
                break
    finally:
        if painter is not None and painter.isActive():
            painter.end()
        prog.close()
    return done


class PrintDialog(QDialog):
    def __init__(self, parent, doc, title: str, current: int, selected: list[int], cfg: dict):
        super().__init__(parent)
        self.setWindowTitle("In tài liệu")
        from .dialogs import fit_dialog
        fit_dialog(self, 1060, 780)
        self.doc = doc
        self.title = title
        self.current = current
        self.selected = selected
        self.cfg = cfg
        self.printer: QPrinter | None = None
        self.sheet = 0
        self.result_printer: QPrinter | None = None
        self.result_opts: PrintOptions | None = None
        n = doc.page_count
        saved = cfg.get("print", {})

        root = QHBoxLayout(self)
        left = QVBoxLayout()
        root.addLayout(left, 0)

        # --- máy in
        g = QGroupBox("Máy in")
        f = QFormLayout(g)
        self.printer_box = QComboBox()
        default = QPrinterInfo.defaultPrinterName()
        for info in QPrinterInfo.availablePrinters():
            self.printer_box.addItem(info.printerName() + ("  (mặc định)" if info.printerName() == default else ""),
                                     info.printerName())
        self.printer_box.addItem("Lưu thành file PDF", PDF_PRINTER)
        want = saved.get("printer") or default
        i = self.printer_box.findData(want)
        self.printer_box.setCurrentIndex(i if i >= 0 else 0)
        f.addRow("Máy in:", self.printer_box)
        row = QHBoxLayout()
        self.copies = QSpinBox()
        self.copies.setRange(1, 999)
        self.collate = QCheckBox("Xếp theo bộ (1,2,3 – 1,2,3)")
        self.collate.setChecked(True)
        row.addWidget(self.copies)
        row.addWidget(self.collate)
        row.addStretch()
        f.addRow("Số bản:", row)
        self.duplex = QComboBox()
        for k, t in (("none", "In một mặt"), ("long", "In hai mặt, lật cạnh dài"), ("short", "In hai mặt, lật cạnh ngắn")):
            self.duplex.addItem(t, k)
        f.addRow("Mặt in:", self.duplex)
        self.gray = QComboBox()
        self.gray.addItem("Màu", False)
        self.gray.addItem("Đen trắng (thang xám)", True)
        f.addRow("Màu sắc:", self.gray)
        left.addWidget(g)

        # --- trang cần in
        g = QGroupBox("Trang cần in")
        f = QFormLayout(g)
        self.range = QComboBox()
        self.range.addItem(f"Tất cả ({n} trang)", "all")
        self.range.addItem(f"Trang đang xem (trang {current + 1})", "current")
        if len(selected) > 1:
            self.range.addItem(f"{len(selected)} trang đang chọn ở thanh bên", "selected")
        self.range.addItem("Tự nhập", "custom")
        f.addRow("Phạm vi:", self.range)
        self.custom = QLineEdit()
        self.custom.setPlaceholderText("Ví dụ: 1-3, 5, 8-")
        f.addRow("Số trang:", self.custom)
        self.subset = QComboBox()
        for k, t in (("all", "Mọi trang trong phạm vi"), ("odd", "Chỉ trang lẻ"), ("even", "Chỉ trang chẵn")):
            self.subset.addItem(t, k)
        f.addRow("Lọc:", self.subset)
        self.reverse = QCheckBox("In ngược từ trang cuối lên")
        f.addRow("", self.reverse)
        left.addWidget(g)

        # --- giấy và bố cục
        g = QGroupBox("Giấy và bố cục")
        f = QFormLayout(g)
        self.paper = QComboBox()
        for k, t in PAPERS:
            self.paper.addItem(t, k)
        f.addRow("Khổ giấy:", self.paper)
        self.orient = QComboBox()
        for k, t in (("auto", "Tự động theo trang"), ("portrait", "Dọc"), ("landscape", "Ngang")):
            self.orient.addItem(t, k)
        f.addRow("Hướng giấy:", self.orient)
        self.scale = QComboBox()
        for k, t in (("fit", "Vừa khít khổ giấy"), ("actual", "Kích thước thật (100%)"),
                     ("shrink", "Chỉ thu nhỏ trang quá khổ"), ("custom", "Tỉ lệ tuỳ chọn")):
            self.scale.addItem(t, k)
        row = QHBoxLayout()
        self.percent = QDoubleSpinBox()
        self.percent.setRange(5, 800)
        self.percent.setDecimals(0)
        self.percent.setValue(100)
        self.percent.setSuffix(" %")
        row.addWidget(self.scale, 1)
        row.addWidget(self.percent)
        f.addRow("Tỉ lệ:", row)
        self.nup = QComboBox()
        for k in (1, 2, 4, 6, 9, 16):
            self.nup.addItem(f"{k} trang trên một tờ", k)
        self.nup.addItem("Sách gập đôi (booklet)", "booklet")
        f.addRow("Gộp trang:", self.nup)
        self.bk_side = QComboBox()
        for k, t in (("both", "Hai mặt tự động (máy in có đảo mặt)"), ("front", "In tay lượt 1: chỉ mặt trước"),
                     ("back", "In tay lượt 2: chỉ mặt sau")):
            self.bk_side.addItem(t, k)
        self.bk_bind = QComboBox()
        self.bk_bind.addItem("Gáy bên trái (sách tiếng Việt, tiếng Anh)", "left")
        self.bk_bind.addItem("Gáy bên phải", "right")
        f.addRow("Booklet:", self.bk_side)
        f.addRow("Gáy sách:", self.bk_bind)
        self.bk_note = QLabel("")
        self.bk_note.setWordWrap(True)
        self.bk_note.setStyleSheet("color:#5f6368")
        self.bk_note.setMaximumWidth(360)
        f.addRow("", self.bk_note)
        self.borders = QCheckBox("Kẻ viền quanh mỗi trang")
        self.center = QCheckBox("Canh giữa tờ giấy")
        self.center.setChecked(True)
        self.annots = QCheckBox("In cả ghi chú, tô sáng, ảnh chữ ký")
        self.annots.setChecked(True)
        f.addRow("", self.borders)
        f.addRow("", self.center)
        f.addRow("", self.annots)
        left.addWidget(g)
        left.addStretch()

        self.summary = QLabel("")
        self.summary.setStyleSheet("color:#3c4043")
        left.addWidget(self.summary)
        row = QHBoxLayout()
        b_sys = QPushButton("Thiết lập máy in…")
        b_sys.setToolTip("Mở hộp thoại của hệ điều hành để chỉnh khay giấy, chất lượng, các tuỳ chọn riêng của máy in")
        b_sys.clicked.connect(self._system_dialog)
        self.b_print = QPushButton("In")
        self.b_print.setDefault(True)
        self.b_print.clicked.connect(self.accept)
        b_cancel = QPushButton("Huỷ")
        b_cancel.clicked.connect(self.reject)
        row.addWidget(b_sys)
        row.addStretch()
        row.addWidget(self.b_print)
        row.addWidget(b_cancel)
        left.addLayout(row)

        # --- xem trước
        right = QVBoxLayout()
        root.addLayout(right, 1)
        from .dialogs import PreviewBox
        self.preview = PreviewBox()
        self.preview.step.connect(self._step)
        self.preview.changed.connect(lambda: self._timer.start())
        right.addWidget(self.preview, 1)
        nav = QHBoxLayout()
        self.b_prev = QPushButton("◀ Trước")
        self.b_next = QPushButton("Sau ▶")
        self.sheet_lb = QLabel("")
        self.sheet_lb.setAlignment(Qt.AlignCenter)
        self.b_prev.clicked.connect(lambda: self._step(-1))
        self.b_next.clicked.connect(lambda: self._step(1))
        nav.addWidget(self.b_prev)
        nav.addWidget(self.sheet_lb, 1)
        nav.addWidget(self.b_next)
        right.addLayout(nav)

        # khôi phục lựa chọn lần trước (trừ phạm vi trang và số bản)
        for box, key in ((self.paper, "paper"), (self.orient, "orientation"), (self.scale, "scale"),
                         (self.nup, "nup"), (self.duplex, "duplex"), (self.gray, "gray"),
                         (self.bk_bind, "binding")):
            if key in saved:
                j = box.findData(saved[key])
                if j >= 0:
                    box.setCurrentIndex(j)
        self.annots.setChecked(saved.get("annots", True))
        self.borders.setChecked(saved.get("borders", False))

        self._timer = QTimer(self, singleShot=True, interval=120, timeout=self._refresh)
        for w in (self.range, self.subset, self.paper, self.orient, self.scale, self.nup, self.gray, self.duplex,
                  self.bk_side, self.bk_bind):
            w.currentIndexChanged.connect(self._changed)
        for w in (self.reverse, self.borders, self.center, self.annots, self.collate):
            w.toggled.connect(self._changed)
        self.custom.textChanged.connect(self._changed)
        self.percent.valueChanged.connect(self._changed)
        self.copies.valueChanged.connect(self._changed)
        self.printer_box.currentIndexChanged.connect(self._printer_changed)
        self._printer_changed()

    # ------------------------------------------------------------ tuỳ chọn
    def _page_list(self) -> list[int]:
        n = self.doc.page_count
        mode = self.range.currentData()
        if mode == "all":
            pages = list(range(n))
        elif mode == "current":
            pages = [self.current]
        elif mode == "selected":
            pages = list(self.selected)
        else:
            pages = tools.parse_ranges(self.custom.text(), n) if self.custom.text().strip() else []
        sub = self.subset.currentData()
        if sub == "odd":
            pages = [p for p in pages if p % 2 == 0]
        elif sub == "even":
            pages = [p for p in pages if p % 2 == 1]
        if self.reverse.isChecked() and self.nup.currentData() != "booklet":
            pages = pages[::-1]
        return pages

    def options(self) -> PrintOptions:
        bk = self.nup.currentData() == "booklet"
        duplex = self.duplex.currentData()
        if bk:  # booklet hai mặt luôn lật theo cạnh ngắn; in tay từng lượt thì in một mặt
            duplex = "short" if self.bk_side.currentData() == "both" else "none"
        return PrintOptions(pages=self._page_list(), copies=self.copies.value(), collate=self.collate.isChecked(),
                            paper=self.paper.currentData(), orientation=self.orient.currentData(),
                            scale=self.scale.currentData(), percent=self.percent.value(),
                            nup=2 if bk else self.nup.currentData(), borders=self.borders.isChecked(),
                            gray=self.gray.currentData(), annots=self.annots.isChecked(),
                            duplex=duplex, center=self.center.isChecked(), booklet=bk,
                            booklet_side=self.bk_side.currentData(), binding=self.bk_bind.currentData(),
                            reverse_sheets=bk and self.reverse.isChecked())

    def _printer_changed(self):
        name = self.printer_box.currentData()
        if name == PDF_PRINTER:
            self.printer = QPrinter(QPrinter.HighResolution)
            self.printer.setOutputFormat(QPrinter.PdfFormat)
            self.printer.setResolution(300)
        else:
            self.printer = QPrinter(QPrinterInfo.printerInfo(name), QPrinter.HighResolution)
        is_pdf = name == PDF_PRINTER
        self.copies.setEnabled(not is_pdf)
        self.collate.setEnabled(not is_pdf)
        self.b_print.setText("Lưu PDF…" if is_pdf else "In")
        self._changed()

    def _changed(self, *_):
        self.custom.setEnabled(self.range.currentData() == "custom")
        one = self.nup.currentData() == 1
        bk = self.nup.currentData() == "booklet"
        is_pdf = self.printer_box.currentData() == PDF_PRINTER
        self.bk_side.setEnabled(bk)
        self.bk_bind.setEnabled(bk)
        self.orient.setEnabled(not bk)
        self.duplex.setEnabled(not bk and not is_pdf)
        self.reverse.setText("In ngược thứ tự các tờ" if bk else "In ngược từ trang cuối lên")
        if not bk:
            self.bk_note.setText("")
        elif self.bk_side.currentData() == "both":
            self.bk_note.setText("In xong gập đôi cả xấp và ghim giữa là thành sách. Máy in phải có in hai mặt; "
                                 "nếu không có, hãy dùng hai lượt in tay.")
        elif self.bk_side.currentData() == "front":
            self.bk_note.setText("Lượt 1: in hết các mặt trước. Sau đó lật xấp giấy, cho lại vào khay rồi in lượt 2.")
        else:
            self.bk_note.setText("Lượt 2: in mặt sau lên xấp giấy vừa in. Nếu thứ tự bị ngược so với lượt 1, "
                                 "tick “In ngược thứ tự các tờ”. Nên in thử 1 tập mỏng trước.")
        self.scale.setEnabled(one)
        self.percent.setEnabled(one and self.scale.currentData() == "custom")
        self.center.setEnabled(one)
        self._timer.start()

    def _step(self, d: int):
        self.sheet += d
        self._refresh()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._timer.start()

    # ------------------------------------------------------------ xem trước
    def _refresh(self):
        try:
            opts = self.options()
            err = ""
        except tools.PdfError as e:
            opts, err = None, str(e)
        sh = sheets(opts) if opts else []
        self.b_print.setEnabled(bool(sh))
        if not sh:
            self.preview.show_text(err or "Chưa có trang nào để in")
            self.sheet_lb.setText("")
            self.summary.setText("")
            self.b_prev.setEnabled(False)
            self.b_next.setEnabled(False)
            return
        self.sheet = max(0, min(self.sheet, len(sh) - 1))
        pages = sh[self.sheet]
        pr = self.printer
        apply_options(pr, opts)
        pr.setPageOrientation(QPageLayout.Landscape if sheet_landscape(self.doc, pages, opts)
                              else QPageLayout.Portrait)
        lay = pr.pageLayout()
        full = lay.fullRect(QPageLayout.Point)
        paint = lay.paintRect(QPageLayout.Point)
        dpr = self.devicePixelRatioF()
        k = self.preview.scale(full.width(), full.height())
        kk = k * dpr  # điểm ảnh vật lý trên mỗi point: kết xuất thẳng ở cỡ này, không kéo giãn
        img = QImage(max(1, round(full.width() * kk)), max(1, round(full.height() * kk)), QImage.Format_RGB32)
        img.fill(Qt.white)
        p = QPainter(img)
        p.setPen(QPen(QColor("#c9d6f0"), 1, Qt.DashLine))  # mép vùng in được của máy in
        p.drawRect(QRectF(round(paint.left() * kk), round(paint.top() * kk), round(paint.width() * kk),
                          round(paint.height() * kk)))
        if opts.booklet:  # vạch gập giữa
            p.setPen(QPen(QColor("#9bb7e8"), 1, Qt.DotLine))
            if full.width() > full.height():
                p.drawLine(round(full.width() * kk / 2), 0, round(full.width() * kk / 2), img.height())
            else:
                p.drawLine(0, round(full.height() * kk / 2), img.width(), round(full.height() * kk / 2))
        p.translate(round(paint.left() * kk), round(paint.top() * kk))
        draw_sheet(p, paint.width() * kk, paint.height() * kk, kk, self.doc, pages, opts, max_dpi=1e9, crisp=True)
        p.end()
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(dpr)
        frame = QPixmap(pm.size() + QSize(int(6 * dpr), int(6 * dpr)))
        frame.setDevicePixelRatio(dpr)
        frame.fill(Qt.transparent)
        fp = QPainter(frame)
        fp.fillRect(QRectF(3, 3, pm.width() / dpr, pm.height() / dpr), QColor(0, 0, 0, 60))
        fp.drawPixmap(0, 0, pm)
        fp.setPen(QColor("#9aa0a6"))
        fp.drawRect(QRectF(0, 0, pm.width() / dpr - 1, pm.height() / dpr - 1))
        fp.end()
        self.preview.show_pixmap(frame)
        label = ", ".join("trắng" if x is None else str(x + 1) for x in pages)
        side = ""
        if opts.booklet and opts.booklet_side == "both":
            side = f" – tờ {self.sheet // 2 + 1} mặt {'trước' if self.sheet % 2 == 0 else 'sau'}"
        self.sheet_lb.setText(f"Mặt {self.sheet + 1} / {len(sh)}{side}   (trang {label})")
        self.b_prev.setEnabled(self.sheet > 0)
        self.b_next.setEnabled(self.sheet < len(sh) - 1)
        size = lay.pageSize()
        mm = size.size(QPageSize.Millimeter)
        w_mm, h_mm = (mm.height(), mm.width()) if full.width() > full.height() else (mm.width(), mm.height())
        papers = math.ceil(len(sh) / 2) if opts.duplex != "none" else len(sh)
        total = papers * (opts.copies if self.copies.isEnabled() else 1)
        self.summary.setText(f"Giấy {size.name()} – {w_mm:.0f} × {h_mm:.0f} mm.  In {len(opts.pages)} trang, "
                             f"cần {total} tờ giấy.")

    # ------------------------------------------------------------ in
    def _system_dialog(self):
        if self.printer_box.currentData() == PDF_PRINTER:
            QMessageBox.information(self, "In", "Mục này chỉ dùng cho máy in thật.")
            return
        d = QPrintDialog(self.printer, self)
        d.setWindowTitle("Thiết lập máy in")
        if d.exec():
            j = self.printer_box.findData(self.printer.printerName())
            if j >= 0 and j != self.printer_box.currentIndex():
                self.printer_box.blockSignals(True)
                self.printer_box.setCurrentIndex(j)
                self.printer_box.blockSignals(False)
            self.copies.setValue(max(1, self.printer.copyCount()))
            self.paper.setCurrentIndex(0)  # giữ khổ giấy vừa chọn trong hộp thoại hệ thống
            self._changed()

    def accept(self):
        try:
            opts = self.options()
        except tools.PdfError as e:
            QMessageBox.warning(self, "In", str(e))
            return
        if not opts.pages:
            return
        if self.printer_box.currentData() == PDF_PRINTER:
            base = self.title[:-4] if self.title.lower().endswith(".pdf") else self.title
            out, _ = QFileDialog.getSaveFileName(self, "Lưu bản in thành PDF", base + "_ban_in.pdf", "PDF (*.pdf)")
            if not out:
                return
            if not out.lower().endswith(".pdf"):
                out += ".pdf"
            self.printer.setOutputFileName(out)
            self.out_file = out
        else:
            self.out_file = None
        self.cfg["print"] = {"printer": "" if self.printer_box.currentData() == PDF_PRINTER
                             else self.printer_box.currentData(), "paper": opts.paper,
                             "orientation": opts.orientation, "scale": opts.scale, "nup": self.nup.currentData(),
                             "bk_side": opts.booklet_side, "binding": opts.binding,
                             "duplex": opts.duplex, "gray": opts.gray, "annots": opts.annots,
                             "borders": opts.borders}
        self.result_printer, self.result_opts = self.printer, opts
        super().accept()
