"""OMOP CDM 5.4 rows, checked against the OHDSI DDL.

The writer knows the CDM's tables from OHDSI's DuckDB DDL for 5.4 (shipped unmodified under `ddl/`): each table's
columns in order, their types, and which are NOT NULL. Rows are written as one CSV per table, with the DDL's column
order as the header, and every call loads them into an in-memory DuckDB database built from that DDL and its primary
keys: a value of the wrong type, a missing NOT NULL column or a duplicate key fails the load, and the call with it.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from sdc_mapper import MappingError

DDL_DIR = Path(__file__).with_name("ddl")
DDL = DDL_DIR / "OMOPCDM_duckdb_5.4_ddl.sql"
PRIMARY_KEYS = DDL_DIR / "OMOPCDM_duckdb_5.4_primary_keys.sql"
SCHEMA = "@cdmDatabaseSchema."


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    required: bool


@lru_cache(maxsize=1)
def tables() -> dict[str, list[Column]]:
    text = DDL.read_text(encoding="utf-8")
    out: dict[str, list[Column]] = {}
    for m in re.finditer(r"CREATE TABLE @cdmDatabaseSchema\.(\w+) \((.*?)\);", text, re.S):
        cols = []
        for line in m.group(2).split(",\n"):
            parts = line.split()
            if len(parts) >= 3:
                cols.append(Column(parts[0], parts[1], "NOT NULL" in line))
        out[m.group(1)] = cols
    return out


def columns(table: str) -> list[Column]:
    t = tables().get(table)
    if t is None:
        raise MappingError(f"OMOP CDM 5.4 has no table {table!r}")
    return t


@dataclass
class Row:
    table: str
    values: dict[str, str] = field(default_factory=dict)
    positions: set[int] = field(default_factory=set)        # values of the record written in this row

    def set(self, column: str, value, *, position: int | None = None, overwrite: bool = False):
        if column not in {c.name for c in columns(self.table)}:
            raise MappingError(f"OMOP CDM 5.4 {self.table} has no column {column!r}")
        value = None if value is None else str(value)
        if column in self.values and self.values[column] != value and not overwrite:
            raise MappingError(f"two values for {self.table}.{column}")
        self.values[column] = value
        if position is not None:
            self.positions.add(position)

    def missing(self) -> list[str]:
        return [c.name for c in columns(self.table) if c.required and self.values.get(c.name) in (None, "")]


def to_csv(rows: list[Row]) -> dict[str, bytes]:
    """One CSV per table, the DDL's columns in order."""
    by_table: dict[str, list[Row]] = {}
    for r in rows:
        by_table.setdefault(r.table, []).append(r)
    files = {}
    for table, rs in by_table.items():
        names = [c.name for c in columns(table)]
        out = io.StringIO()
        w = csv.writer(out, lineterminator="\n")
        w.writerow(names)
        for r in rs:
            w.writerow(["" if r.values.get(n) is None else r.values[n] for n in names])
        files[f"{table}.csv"] = out.getvalue().encode("utf-8")
    return files


def ddl_statements() -> list[str]:
    text = DDL.read_text(encoding="utf-8") + "\n" + PRIMARY_KEYS.read_text(encoding="utf-8")
    text = re.sub(r"^--.*$", "", text, flags=re.M).replace(SCHEMA, "")
    return [s.strip() for s in text.split(";") if s.strip()]


def load(files: dict[str, bytes], con=None):
    """Load the CSVs into a DuckDB database built from the OHDSI DDL; any failure is a MappingError. Pass `con` (a
    connection already holding the CDM's tables) to load many records into one database."""
    import duckdb
    if con is None:
        con = duckdb.connect(":memory:")
        for s in ddl_statements():
            con.execute(s)
    for name, data in files.items():
        table = name.removesuffix(".csv")
        cols = [c for c in columns(table)]
        reader = csv.reader(io.StringIO(data.decode("utf-8")))
        header = next(reader)
        placeholders = ", ".join("?" for _ in header)
        try:
            for row in reader:
                con.execute(f"INSERT INTO {table} ({', '.join(header)}) VALUES ({placeholders})",
                            [None if v == "" else v for v in row])
        except Exception as e:      # the DDL's types, NOT NULLs and keys: the database's word, not ours
            raise MappingError(f"OMOP CDM 5.4 {table} refused the row: {e}") from e
        assert [c.name for c in cols] == header
    return con
