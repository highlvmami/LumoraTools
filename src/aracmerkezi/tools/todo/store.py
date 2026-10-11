"""Yapılacaklar listesi deposu (SQLite). Tk'den bağımsızdır, tek başına test edilebilir."""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from ...datefilter import parse_date
from ...textutil import fold

PRIORITIES = {0: "Normal", 1: "Yüksek", 2: "Acil"}
FILTERS = ("open", "today", "overdue", "done", "all")
_UNSET = object()


@dataclass(frozen=True)
class Task:
    id: int
    title: str
    notes: str
    done: bool
    priority: int
    due: str | None            # YYYY-AA-GG
    created: float
    done_at: float | None


def parse_due(text: str | None) -> str | None:
    """Kullanıcının yazdığı tarihi (GG.AA.YYYY vb.) YYYY-AA-GG'ye çevirir; boşsa None; geçersizse ValueError."""
    parsed = parse_date(text or "")
    return parsed.date().isoformat() if parsed else None


def due_status(task: Task, today: date | None = None) -> str:
    """'overdue' (gecikmiş), 'today' (bugün), 'soon' (2 gün içinde) ya da '' (yok / bitmiş / uzak)."""
    if task.done or not task.due:
        return ""
    today = today or date.today()
    delta = (date.fromisoformat(task.due) - today).days
    return "overdue" if delta < 0 else "today" if delta == 0 else "soon" if delta <= 2 else ""


class TodoStore:
    def __init__(self, path: Path | str) -> None:
        self.db = sqlite3.connect(str(path))
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',"
            " done INTEGER NOT NULL DEFAULT 0, priority INTEGER NOT NULL DEFAULT 0, due TEXT,"
            " created REAL NOT NULL, done_at REAL)")
        self.db.commit()

    @staticmethod
    def _row(r) -> Task:
        return Task(r[0], r[1], r[2], bool(r[3]), r[4], r[5], r[6], r[7])

    _COLS = "id, title, notes, done, priority, due, created, done_at"

    def add(self, title: str, due: str | None = None, priority: int = 0, notes: str = "") -> int:
        title = title.strip()
        if not title:
            raise ValueError("Görev başlığı boş olamaz.")
        if priority not in PRIORITIES:
            raise ValueError("Geçersiz öncelik.")
        cur = self.db.execute("INSERT INTO tasks(title, notes, priority, due, created) VALUES(?, ?, ?, ?, ?)",
                              (title, notes.strip(), priority, due, time.time()))
        self.db.commit()
        return cur.lastrowid

    def get(self, task_id: int) -> Task | None:
        r = self.db.execute(f"SELECT {self._COLS} FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row(r) if r else None

    def update(self, task_id: int, title: str | None = None, notes: str | None = None, priority: int | None = None,
               due=_UNSET) -> None:
        sets, args = [], []
        if title is not None:
            if not title.strip():
                raise ValueError("Görev başlığı boş olamaz.")
            sets.append("title = ?"), args.append(title.strip())
        if notes is not None:
            sets.append("notes = ?"), args.append(notes.strip())
        if priority is not None:
            if priority not in PRIORITIES:
                raise ValueError("Geçersiz öncelik.")
            sets.append("priority = ?"), args.append(priority)
        if due is not _UNSET:
            sets.append("due = ?"), args.append(due)
        if sets:
            self.db.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", (*args, task_id))
            self.db.commit()

    def toggle(self, task_id: int) -> bool:
        """Bitti/bitmedi durumunu değiştirir; yeni durumu (True = bitti) döndürür."""
        task = self.get(task_id)
        if task is None:
            raise KeyError(task_id)
        done = not task.done
        self.db.execute("UPDATE tasks SET done = ?, done_at = ? WHERE id = ?", (int(done), time.time() if done else None, task_id))
        self.db.commit()
        return done

    def delete(self, task_id: int) -> None:
        self.db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.db.commit()

    def clear_done(self) -> int:
        n = self.db.execute("DELETE FROM tasks WHERE done = 1").rowcount
        self.db.commit()
        return n

    def list(self, flt: str = "open", query: str = "", today: date | None = None) -> list[Task]:
        """Süzgece göre görevler. Açık görevler: öncelik (acil önce), sonra son tarihi yakın olan, sonra eskisi önce.
        Biten görevler: en son bitirilen önce."""
        if flt not in FILTERS:
            raise ValueError(f"Bilinmeyen süzgeç: {flt}")
        today_iso = (today or date.today()).isoformat()
        rows = [self._row(r) for r in self.db.execute(f"SELECT {self._COLS} FROM tasks")]
        if flt == "open":
            rows = [t for t in rows if not t.done]
        elif flt == "done":
            rows = [t for t in rows if t.done]
        elif flt == "today":
            rows = [t for t in rows if not t.done and t.due == today_iso]
        elif flt == "overdue":
            rows = [t for t in rows if not t.done and t.due and t.due < today_iso]
        needle = fold(query.strip())
        if needle:
            rows = [t for t in rows if needle in fold(t.title) or needle in fold(t.notes)]
        if flt == "done":
            rows.sort(key=lambda t: -(t.done_at or 0))
        else:
            rows.sort(key=lambda t: (t.done, -t.priority, t.due is None, t.due or "", t.created))
        return rows

    def counts(self, today: date | None = None) -> dict[str, int]:
        return {f: len(self.list(f, today=today)) for f in ("open", "today", "overdue", "done")}

    def close(self) -> None:
        self.db.close()


def format_due(due: str | None) -> str:
    return datetime.fromisoformat(due).strftime("%d.%m.%Y") if due else ""
