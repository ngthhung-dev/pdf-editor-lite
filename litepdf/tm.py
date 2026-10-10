"""Bộ nhớ dịch: lưu từng cặp (câu gốc → câu dịch) trên máy để lần sau dùng lại ngay, không phải gọi máy dịch."""
from __future__ import annotations

import json
import os
import sqlite3
import time


def _norm(text: str) -> str:
    return " ".join(text.split())


class Memory:
    def __init__(self, folder: str):
        self.path = os.path.join(folder, "bo_nho_dich.db")
        self.db = sqlite3.connect(self.path)
        self.db.execute("CREATE TABLE IF NOT EXISTS tm (target TEXT NOT NULL, src TEXT NOT NULL, dst TEXT NOT NULL, "
                        "origin TEXT, ts REAL, PRIMARY KEY (target, src))")
        self.db.execute("CREATE TABLE IF NOT EXISTS ocr (engine TEXT NOT NULL, key TEXT NOT NULL, lines TEXT NOT NULL, "
                        "ts REAL, PRIMARY KEY (engine, key))")
        self.db.commit()

    # chữ đã đọc được trong từng hình ảnh: lần sau dịch lại cùng tài liệu khỏi phải nhận dạng lại
    def ocr_get(self, engine: str, key: str):
        row = self.db.execute("SELECT lines FROM ocr WHERE engine=? AND key=?", (engine, key)).fetchone()
        if not row:
            return None
        try:
            return [(tuple(b), t) for b, t in json.loads(row[0])]
        except Exception:
            return None

    def ocr_put(self, engine: str, key: str, lines: list):
        self.db.execute("INSERT OR REPLACE INTO ocr (engine, key, lines, ts) VALUES (?,?,?,?)",
                        (engine, key, json.dumps([[list(b), t] for b, t in lines], ensure_ascii=False), time.time()))
        self.db.commit()

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM tm").fetchone()[0]

    def lookup(self, target: str, texts: list[str]) -> list[str | None]:
        """Bản dịch đã lưu của từng câu (None nếu chưa có)."""
        keys = list({_norm(t) for t in texts})
        found: dict[str, str] = {}
        for i in range(0, len(keys), 400):
            part = keys[i:i + 400]
            q = "SELECT src, dst FROM tm WHERE target=? AND src IN (%s)" % ",".join("?" * len(part))
            found.update(self.db.execute(q, [target] + part).fetchall())
        return [found.get(_norm(t)) for t in texts]

    def store(self, target: str, pairs: list[tuple[str, str]], origin: str = "machine") -> int:
        """Lưu các cặp câu. Câu người dùng tự sửa (origin='manual') không bị bản dịch máy ghi đè."""
        rows = [(target, _norm(s), d.strip(), origin, time.time()) for s, d in pairs
                if s and d and d.strip() and _norm(s) != _norm(d)]
        if not rows:
            return 0
        guard = "" if origin == "manual" else " WHERE tm.origin IS NOT 'manual'"
        self.db.executemany("INSERT INTO tm (target, src, dst, origin, ts) VALUES (?,?,?,?,?) ON CONFLICT(target, src) "
                            "DO UPDATE SET dst=excluded.dst, origin=excluded.origin, ts=excluded.ts" + guard, rows)
        self.db.commit()
        return len(rows)

    def clear(self):
        self.db.execute("DELETE FROM tm")
        self.db.execute("DELETE FROM ocr")
        self.db.commit()
        self.db.execute("VACUUM")


_mem: Memory | None = None


def memory(folder: str) -> Memory:
    global _mem
    if _mem is None:
        _mem = Memory(folder)
    return _mem
