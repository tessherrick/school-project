"""Tiny in-memory stand-in for the Supabase client.

Implements just enough of the chained query API to exercise the ML
package end-to-end: select / eq / gte / lte / insert / upsert / update.
Rows are stored as plain dicts in self.tables[name].
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4


class _Result:
    def __init__(self, data: list[dict[str, Any]]):
        self.data = data


class _Query:
    def __init__(self, db: "FakeSupabase", table: str):
        self.db = db
        self.table = table
        self._mode: str | None = None
        self._payload: Any = None
        self._on_conflict: str | None = None
        self._filters: list[tuple[str, str, Any]] = []

    def select(self, _cols: str = "*") -> "_Query":
        self._mode = "select"
        return self

    def insert(self, row: dict[str, Any] | list[dict[str, Any]]) -> "_Query":
        self._mode = "insert"
        self._payload = row if isinstance(row, list) else [row]
        return self

    def upsert(
        self,
        row: dict[str, Any] | list[dict[str, Any]],
        on_conflict: str | None = None,
    ) -> "_Query":
        self._mode = "upsert"
        self._payload = row if isinstance(row, list) else [row]
        self._on_conflict = on_conflict
        return self

    def update(self, patch: dict[str, Any]) -> "_Query":
        self._mode = "update"
        self._payload = patch
        return self

    def eq(self, col: str, val: Any) -> "_Query":
        self._filters.append(("eq", col, val))
        return self

    def gte(self, col: str, val: Any) -> "_Query":
        self._filters.append(("gte", col, val))
        return self

    def lte(self, col: str, val: Any) -> "_Query":
        self._filters.append(("lte", col, val))
        return self

    def order(self, _col: str, desc: bool = False) -> "_Query":
        return self

    def limit(self, _n: int) -> "_Query":
        return self

    def _matches(self, row: dict[str, Any]) -> bool:
        for op, col, val in self._filters:
            cell = row.get(col)
            if op == "eq" and cell != val:
                return False
            if op == "gte" and (cell is None or str(cell) < str(val)):
                return False
            if op == "lte" and (cell is None or str(cell) > str(val)):
                return False
        return True

    def execute(self) -> _Result:
        rows = self.db.tables.setdefault(self.table, [])
        if self._mode == "select":
            return _Result([deepcopy(r) for r in rows if self._matches(r)])
        if self._mode == "insert":
            inserted = []
            for r in self._payload:
                row = deepcopy(r)
                row.setdefault("id", str(uuid4()))
                rows.append(row)
                inserted.append(deepcopy(row))
            return _Result(inserted)
        if self._mode == "upsert":
            keys = (self._on_conflict or "").split(",") if self._on_conflict else []
            keys = [k.strip() for k in keys if k.strip()]
            updated = []
            for r in self._payload:
                row = deepcopy(r)
                match_idx = None
                if keys:
                    for i, existing in enumerate(rows):
                        if all(existing.get(k) == row.get(k) for k in keys):
                            match_idx = i
                            break
                if match_idx is not None:
                    rows[match_idx].update(row)
                    updated.append(deepcopy(rows[match_idx]))
                else:
                    row.setdefault("id", str(uuid4()))
                    rows.append(row)
                    updated.append(deepcopy(row))
            return _Result(updated)
        if self._mode == "update":
            patched = []
            for row in rows:
                if self._matches(row):
                    row.update(self._payload)
                    patched.append(deepcopy(row))
            return _Result(patched)
        raise RuntimeError(f"Unhandled query mode: {self._mode}")


class FakeSupabase:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}

    def table(self, name: str) -> _Query:
        self.tables.setdefault(name, [])
        return _Query(self, name)
