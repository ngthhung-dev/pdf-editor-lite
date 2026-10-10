"""Bảng bookmark (mục lục) của tài liệu: xem, tạo, đổi tên, sắp xếp, xoá."""
from __future__ import annotations

import pymupdf

from .icons import icon, icon_for
from PySide6.QtCore import QPointF, QRect, QSize, Qt, QTimer
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QStyledItemDelegate,
                               QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

PAGE = Qt.UserRole
DEST = Qt.UserRole + 1


class _Tree(QTreeWidget):
    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    def dropEvent(self, e):
        super().dropEvent(e)
        self.panel.commit()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Delete and self.currentItem():
            self.panel.delete()
        else:
            super().keyPressEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.panel.wrap:
            self.scheduleDelayedItemsLayout()      # đổi độ rộng thì tính lại chỗ xuống dòng


class _WrapDelegate(QStyledItemDelegate):
    """Cho tên bookmark dài tự xuống dòng (khi bật tuỳ chọn) thay vì bị cắt bằng dấu …"""

    def __init__(self, tree, panel):
        super().__init__(tree)
        self.tree, self.panel = tree, panel

    def sizeHint(self, opt, index):
        base = super().sizeHint(opt, index)
        if not self.panel.wrap:
            return base
        depth, p = 1, index.parent()
        while p.isValid():
            depth, p = depth + 1, p.parent()
        w = max(60, self.tree.viewport().width() - self.tree.indentation() * depth - 10)
        r = opt.fontMetrics.boundingRect(QRect(0, 0, w, 10000), Qt.TextWordWrap, str(index.data() or ""))
        return QSize(w, max(base.height(), r.height() + 6))


class BookmarkPanel(QWidget):
    def __init__(self, model, viewer, cfg=None):
        super().__init__()
        self.model = model
        self.viewer = viewer
        self.loading = False
        self.committing = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.cfg = cfg if cfg is not None else {}
        self.wrap = bool(self.cfg.get("bm_wrap", False))
        self.hide_after = bool(self.cfg.get("bm_hide_after", False))
        self.host = None            # (cửa sổ chính, tab) để gọi các chức năng tạo bookmark tự động
        self.hide_side = None       # hàm ẩn thanh bên (dùng cho "Ẩn bảng sau khi bấm")
        title = QLabel("Bookmark")
        title.setStyleSheet("QLabel{font-weight:600;color:#3c4043;padding:6px 6px 0 6px;}")
        lay.addWidget(title)
        bar = QHBoxLayout()
        bar.setContentsMargins(4, 2, 4, 0)
        bar.setSpacing(1)
        self.b_menu = QToolButton()
        self.b_menu.setIcon(icon("listmenu"))
        self.b_menu.setToolTip("Tuỳ chọn bookmark")
        self.b_menu.setPopupMode(QToolButton.InstantPopup)
        self.b_menu.setStyleSheet("QToolButton::menu-indicator{image:none;}")
        self.opt_menu = QMenu(self)
        self.opt_menu.aboutToShow.connect(self._fill_options)
        self.b_menu.setMenu(self.opt_menu)
        buttons = [(self.b_menu, None)]
        for name, tip, fn in (("bookmark_add", "Thêm bookmark tại vị trí đang xem (Ctrl+B)", self.add),
                              ("bookmark_child", "Thêm bookmark con của mục đang chọn (Ctrl+Shift+B)", lambda: self.add(child=True)),
                              ("editnote", "Đổi tên bookmark đang chọn (F2 hoặc bấm đúp)", self.rename),
                              ("delete", "Xoá bookmark đang chọn (Delete)", self.delete)):
            b = QToolButton()
            b.setIcon(icon(name))
            b.setToolTip(tip)
            b.clicked.connect(fn)
            buttons.append((b, name))
        for k, (b, _n) in enumerate(buttons):
            b.setIconSize(QSize(20, 20))
            b.setFixedSize(28, 26)
            b.setAutoRaise(True)
            bar.addWidget(b)
            if k == 0:
                bar.addSpacing(6)
        bar.addStretch()
        lay.addLayout(bar)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm bookmark…")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(icon("search"), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self._filter)
        box = QHBoxLayout()
        box.setContentsMargins(6, 3, 6, 3)
        box.addWidget(self.search)
        lay.addLayout(box)
        self.tree = _Tree(self)
        self.tree.setHeaderHidden(True)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.setEditTriggers(QAbstractItemView.EditKeyPressed | QAbstractItemView.DoubleClicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        self.tree.itemClicked.connect(self._goto)
        self.tree.itemChanged.connect(self._renamed)
        self.tree.setStyleSheet("QTreeWidget{border:none;}")
        self.tree.setItemDelegate(_WrapDelegate(self.tree, self))
        self._apply_wrap()
        lay.addWidget(self.tree, 1)
        # luôn tô sáng bookmark ứng với chỗ đang xem khi cuộn trang
        self._quiet_until = 0.0
        self._follow = QTimer(self, singleShot=True, interval=120, timeout=self.sync_to_view)
        viewer.verticalScrollBar().valueChanged.connect(lambda *_: self._follow.start())
        self.load()

    # ------------------------------------------------------------ đọc / ghi
    def _item(self, title: str, page: int, dest: dict | None) -> QTreeWidgetItem:
        it = QTreeWidgetItem([title])
        it.setFlags(it.flags() | Qt.ItemIsEditable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
        it.setData(0, PAGE, page)
        it.setData(0, DEST, dest)
        it.setToolTip(0, f"Trang {page + 1}" if page >= 0 else "Liên kết ngoài")
        return it

    def load(self):
        self.loading = True
        self.tree.clear()
        try:
            toc = self.model.doc.get_toc(simple=False)
        except Exception:
            toc = []
        stack: list[tuple[int, QTreeWidgetItem]] = []
        collapsed = []
        for lvl, title, page, dest in toc:
            while stack and stack[-1][0] >= lvl:
                stack.pop()
            parent = stack[-1][1] if stack else self.tree.invisibleRootItem()
            d = {k: v for k, v in (dest or {}).items() if k != "xref"}
            it = self._item(title, page - 1, d)
            parent.addChild(it)
            if d.get("collapse"):
                collapsed.append(it)
            stack.append((lvl, it))
        self.tree.expandAll()
        for it in collapsed:
            it.setExpanded(False)
        self.loading = False

    def _toc(self) -> list:
        out = []

        def walk(parent, lvl):
            for i in range(parent.childCount()):
                it = parent.child(i)
                page = it.data(0, PAGE)
                dest = dict(it.data(0, DEST) or {})
                title = it.text(0).strip() or "Không tên"
                if dest.get("kind", pymupdf.LINK_GOTO) == pymupdf.LINK_GOTO:
                    dest["kind"] = pymupdf.LINK_GOTO
                    dest.setdefault("to", pymupdf.Point(0, 0))
                    dest.pop("page", None)
                dest["collapse"] = it.childCount() > 0 and not it.isExpanded()
                out.append([lvl, title, page + 1, dest])
                walk(it, lvl + 1)
        walk(self.tree.invisibleRootItem(), 1)
        return out

    def commit(self):
        """Ghi cây bookmark hiện tại vào tài liệu (hoàn tác được bằng Ctrl+Z)."""
        if self.loading:
            return
        toc = self._toc()
        self.committing = True
        try:
            with self.model.edit("toc"):
                self.model.doc.set_toc(toc)
        except Exception as e:
            self.committing = False
            QMessageBox.warning(self, "Bookmark", f"Không ghi được bookmark:\n{e}")
            self.load()
            return
        self.committing = False

    def count(self) -> int:
        return len(self._toc())

    # ------------------------------------------------------------ thao tác
    def _here(self) -> tuple[int, pymupdf.Point]:
        """Trang và điểm (toạ độ trang) ứng với chỗ đang xem; ưu tiên chỗ có chữ đang chọn."""
        v = self.viewer
        if v.sel_rects and v.sel_page is not None:
            r = v.sel_rects[0]
            return v.sel_page, pymupdf.Point(0, max(0, r.y0 - 12))
        i = v.current_page()
        top = v.mapToScene(0, 0).y()
        rect = v.rects[i]
        y = min(max(top, rect.top()), rect.bottom() - 1)
        return i, v.to_page(i, QPointF(rect.left(), y))

    def add(self, child: bool = False, title: str | None = None):
        if not self.viewer.rects:
            return
        page, pt = self._here()
        if title is None:
            sel = (self.viewer.sel_text or "").strip().split("\n")[0][:90]
            title = sel or f"Trang {page + 1}"
        it = self._item(title, page, {"kind": pymupdf.LINK_GOTO, "to": pt})
        cur = self.tree.currentItem()
        self.loading = True
        if cur is None:
            self.tree.addTopLevelItem(it)
        elif child:
            cur.addChild(it)
            cur.setExpanded(True)
        else:
            parent = cur.parent() or self.tree.invisibleRootItem()
            parent.insertChild(parent.indexOfChild(cur) + 1, it)
        self.loading = False
        self.commit()
        self.tree.setCurrentItem(it)
        self.tree.editItem(it, 0)

    def rename(self):
        it = self.tree.currentItem()
        if it:
            self.tree.editItem(it, 0)

    def _renamed(self, it, _col):
        if not self.loading:
            if not it.text(0).strip():
                self.loading = True
                it.setText(0, "Không tên")
                self.loading = False
            self.commit()

    def delete(self):
        it = self.tree.currentItem()
        if not it:
            return
        if it.childCount() and QMessageBox.question(
                self, "Bookmark", f"Xoá “{it.text(0)}” cùng {it.childCount()} mục con bên trong?") != QMessageBox.Yes:
            return
        parent = it.parent() or self.tree.invisibleRootItem()
        self.loading = True
        parent.removeChild(it)
        self.loading = False
        self.commit()

    def clear_all(self):
        self.loading = True
        self.tree.clear()
        self.loading = False
        self.commit()

    def _take(self, it):
        parent = it.parent() or self.tree.invisibleRootItem()
        idx = parent.indexOfChild(it)
        expanded = it.isExpanded()
        parent.takeChild(idx)
        return parent, idx, expanded

    def move(self, d: int):
        it = self.tree.currentItem()
        if not it:
            return
        parent = it.parent() or self.tree.invisibleRootItem()
        idx = parent.indexOfChild(it)
        if not 0 <= idx + d < parent.childCount():
            return
        self.loading = True
        _p, _i, ex = self._take(it)
        parent.insertChild(idx + d, it)
        it.setExpanded(ex)
        self.loading = False
        self.tree.setCurrentItem(it)
        self.commit()

    def indent(self):
        it = self.tree.currentItem()
        if not it:
            return
        parent = it.parent() or self.tree.invisibleRootItem()
        idx = parent.indexOfChild(it)
        if idx == 0:
            return
        new_parent = parent.child(idx - 1)
        self.loading = True
        _p, _i, ex = self._take(it)
        new_parent.addChild(it)
        new_parent.setExpanded(True)
        it.setExpanded(ex)
        self.loading = False
        self.tree.setCurrentItem(it)
        self.commit()

    def outdent(self):
        it = self.tree.currentItem()
        if not it or it.parent() is None:
            return
        parent = it.parent()
        grand = parent.parent() or self.tree.invisibleRootItem()
        self.loading = True
        _p, _i, ex = self._take(it)
        grand.insertChild(grand.indexOfChild(parent) + 1, it)
        it.setExpanded(ex)
        self.loading = False
        self.tree.setCurrentItem(it)
        self.commit()

    def retarget(self):
        it = self.tree.currentItem()
        if not it:
            return
        page, pt = self._here()
        self.loading = True
        it.setData(0, PAGE, page)
        it.setData(0, DEST, {"kind": pymupdf.LINK_GOTO, "to": pt})
        it.setToolTip(0, f"Trang {page + 1}")
        self.loading = False
        self.commit()

    def _key(self, it):
        """(trang, vị trí dọc trên trang) mà bookmark trỏ tới; None nếu là liên kết ngoài."""
        page = it.data(0, PAGE)
        if page is None or page < 0 or page >= len(self.viewer.rects):
            return None
        y = 0.0
        to = (it.data(0, DEST) or {}).get("to")
        if to is not None:
            try:
                y = max(0.0, self.viewer.to_display(page, to).y)
            except Exception:
                y = 0.0
        return page, y

    def showEvent(self, e):
        super().showEvent(e)
        # vừa chuyển từ tab Trang sang tab Bookmark (hoặc vừa mở thanh bên): tô sáng ngay bookmark của chỗ đang xem
        self.resync()

    def resync(self):
        """Tô sáng lại bookmark của chỗ đang xem: làm ngay, và làm lại sau khi khung xem đã co giãn xong."""
        for ms in (0, 180, 450):
            QTimer.singleShot(ms, lambda: self.sync_to_view(force=True))

    def sync_to_view(self, force: bool = False):
        """Chọn (tô sáng) bookmark gần nhất nằm ở trên hoặc ngay tại chỗ đang xem."""
        import time
        v = self.viewer
        if self.loading or self.committing or not v.rects or self.tree.topLevelItemCount() == 0:
            return
        if not force and (not self.isVisible() or time.time() < self._quiet_until
                          or self.tree.state() == QAbstractItemView.EditingState):
            return
        sy = v.mapToScene(0, int(v.viewport().height() * 0.3)).y()
        page = v.current_page()
        for i, r in enumerate(v.rects):
            if r.top() <= sy:
                page = i
        here = (page, sy - v.rects[page].top() + 2)
        best = None
        for it in self._all_items_in_order():
            k = self._key(it)
            if k is not None and k <= here and (best is None or k >= best[0]):
                best = (k, it)
        cur = self.tree.currentItem()
        if best is None:      # đang ở trước bookmark đầu tiên (ví dụ trang bìa): không mục nào ứng với chỗ này → bỏ tô sáng
            if cur is not None:
                self.tree.setCurrentItem(None)
                self.tree.clearSelection()
                self.tree.scrollToTop()
            return
        if cur is not None and self._key(cur) == best[0]:
            best = (best[0], cur)                 # nhiều bookmark cùng một chỗ: giữ mục người dùng đang chọn
        if best[1] is not cur:
            p = best[1].parent()
            while p is not None:
                p.setExpanded(True)
                p = p.parent()
            self.tree.setCurrentItem(best[1])
        if force or best[1] is not cur:
            self.tree.scrollToItem(best[1])

    def _all_items_in_order(self):
        out = []

        def walk(p):
            for i in range(p.childCount()):
                out.append(p.child(i))
                walk(p.child(i))
        walk(self.tree.invisibleRootItem())
        return out

    def _goto(self, it, _col=0):
        import time
        self._quiet_until = time.time() + 0.5      # vừa bấm vào bookmark: không để việc cuộn tới nơi đổi lựa chọn
        page = it.data(0, PAGE)
        if page is None or page < 0 or page >= len(self.viewer.rects):
            return
        dest = it.data(0, DEST) or {}
        y = 0.0
        to = dest.get("to")
        if to is not None:
            try:
                y = max(0.0, self.viewer.to_display(page, to).y)
            except Exception:
                y = 0.0
        self.viewer.goto_page(page, y)
        if self.hide_after and self.hide_side:
            self.hide_side()

    # ------------------------------------------------------------ tuỳ chọn, tìm kiếm
    def _apply_wrap(self):
        self.tree.setWordWrap(self.wrap)
        self.tree.setUniformRowHeights(not self.wrap)
        self.tree.setTextElideMode(Qt.ElideNone if self.wrap else Qt.ElideRight)
        self.tree.scheduleDelayedItemsLayout()

    def _set_opt(self, key: str, on: bool):
        setattr(self, "wrap" if key == "bm_wrap" else "hide_after", on)
        self.cfg[key] = on
        if hasattr(self.cfg, "save"):
            self.cfg.save()
        self._apply_wrap()

    def _all_items(self):
        out, stack = [], [self.tree.invisibleRootItem()]
        while stack:
            p = stack.pop()
            for i in range(p.childCount()):
                out.append(p.child(i))
                stack.append(p.child(i))
        return out

    def _toggle_expand(self):
        items = [it for it in self._all_items() if it.childCount()]
        if any(not it.isExpanded() for it in items):
            self.tree.expandAll()
        else:
            self.tree.collapseAll()

    def _filter(self, text: str):
        """Chỉ hiện các bookmark có chứa chữ đang tìm (và các mục cha của chúng)."""
        key = text.strip().lower()

        def walk(it) -> bool:
            hit = key in it.text(0).lower()
            child_hit = False
            for i in range(it.childCount()):
                child_hit = walk(it.child(i)) or child_hit
            it.setHidden(bool(key) and not (hit or child_hit))
            if key and child_hit:
                it.setExpanded(True)
            return hit or child_hit
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            walk(root.child(i))

    def _fill_options(self):
        m = self.opt_menu
        m.clear()
        has = self.tree.topLevelItemCount() > 0
        cur = self.tree.currentItem() is not None
        main, tab = self.host if self.host else (None, None)
        m.addAction(icon("bookmark_add"), "Thêm bookmark", self.add)
        if main is not None:
            m.addAction(icon("bookmark_auto"), "Tự tạo bookmark từ các tiêu đề…", main.guard(lambda: main.bookmark_auto(tab)))
            m.addAction(icon("bookmark_pages"), "Tạo bookmark cho từng trang", main.guard(lambda: main.bookmark_pages(tab)))
        m.addSeparator()
        for text, name, fn in (("Chuyển lên", "up", lambda: self.move(-1)), ("Chuyển xuống", "down", lambda: self.move(1)),
                               ("Thụt vào làm mục con", "indent", self.indent), ("Đưa ra ngoài một cấp", "outdent", self.outdent)):
            m.addAction(icon(name), text, fn).setEnabled(cur)
        m.addSeparator()
        parents = [it for it in self._all_items() if it.childCount()]
        closed = any(not it.isExpanded() for it in parents)      # còn mục đang gập → mời "Mở rộng"; đã mở hết → "Thu gọn"
        m.addAction(icon("expandall" if closed else "collapseall"),
                    "Mở rộng tất cả" if closed else "Thu gọn tất cả", self._toggle_expand).setEnabled(bool(parents))
        a = m.addAction("Xuống dòng với tên bookmark dài")
        a.setCheckable(True)
        a.setChecked(self.wrap)
        a.toggled.connect(lambda on: self._set_opt("bm_wrap", on))
        a = m.addAction("Ẩn bảng sau khi bấm vào bookmark")
        a.setCheckable(True)
        a.setChecked(self.hide_after)
        a.toggled.connect(lambda on: self._set_opt("bm_hide_after", on))
        if main is not None:
            m.addSeparator()
            m.addAction(icon("bookmark_del"), "Xoá tất cả bookmark", main.guard(lambda: main.bookmark_clear(tab))).setEnabled(has)

    def _menu(self, pos):
        it = self.tree.itemAt(pos)
        if it:
            self.tree.setCurrentItem(it)
        m = QMenu(self)
        m.addAction(icon_for("Thêm bookmark tại vị trí đang xem"), "Thêm bookmark tại vị trí đang xem", self.add)
        if it:
            m.addAction(icon_for("Thêm bookmark con"), "Thêm bookmark con", lambda: self.add(child=True))
            m.addSeparator()
            m.addAction(icon_for("Đổi tên"), "Đổi tên", self.rename)
            m.addAction(icon_for("Trỏ lại về vị trí đang xem"), "Đặt lại đích của bookmark này = vị trí đang xem", self.retarget)
            m.addAction(icon_for("Xoá"), "Xoá", self.delete)
            m.addSeparator()
            m.addAction(icon_for("Chuyển lên"), "Chuyển lên", lambda: self.move(-1))
            m.addAction(icon_for("Chuyển xuống"), "Chuyển xuống", lambda: self.move(1))
            m.addAction(icon_for("Thụt vào làm mục con"), "Thụt vào làm mục con", self.indent)
            m.addAction(icon_for("Đưa ra ngoài một cấp"), "Đưa ra ngoài một cấp", self.outdent)
        m.exec(self.tree.mapToGlobal(pos))
