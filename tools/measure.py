"""Measure how the sample records reach OMOP CDM 5.4: the share of values that are lookups (the concept is the
model's), declared (the mapping placed them), carried (text only) and not representable, and of Exceptional Values
preserved, degraded, carried and lost. The PRD makes this measurement the test of whether OMOP stays in the line.

    python tools/measure.py            # Markdown tables, as in the README
"""
from __future__ import annotations

import sys
import tempfile
from collections import Counter
from pathlib import Path

from sdc_mapper import EV_CLASSES, VALUE_CLASSES, Engine, load_mapping
from sdc_gdr2omop import OMOPMapper, mapping_path

ROOT = Path(__file__).resolve().parents[1]
MODELS = [("NHANES Participant", "nhanes-participant", "xy8upneajsb8vdcmnve01g6g"),
          ("NHANES Medication", "nhanes-medication", "epbdfmvxc3gbh5f66hhb3o2m")]
RECORD_CLUSTERS = {"Audit Event", "PROV Activity", "PROV Agent", "PROV Entity"}


def main() -> int:
    engine = Engine(schema_dir=tempfile.mkdtemp())
    mapper = OMOPMapper()
    totals, data_totals, evs = Counter(), Counter(), Counter()
    lines = ["| Model | Records | Values | Lookup | Declared | Carried | Not representable |", "|---|---|---|---|---|---|---|"]
    data_lines = list(lines)
    for title, sample, ct in MODELS:
        mapping = load_mapping(mapping_path(ct))
        counts, data = Counter(), Counter()
        files = sorted((ROOT / "samples" / sample / "records").glob("*.xml"))
        for f in files:
            r = engine.map_record(f.read_bytes(), mapper, mapping, directory=str(ROOT / "samples" / sample))
            if r.outcome == "error":
                print(f"{f.name}: {r.errors}", file=sys.stderr)
                return 1
            for v in r.report.values:
                counts[v["class"]] += 1
                if not RECORD_CLUSTERS & set(v["path"]):
                    data[v["class"]] += 1
            for e in r.report.exceptional:
                evs[e["class"]] += 1
        totals.update(counts)
        data_totals.update(data)
        lines.append(_row(title, len(files), counts))
        data_lines.append(_row(title, len(files), data))
    n = sum(len(list((ROOT / "samples" / s / "records").glob("*.xml"))) for _, s, _ in MODELS)
    lines.append(_row("**All**", n, totals))
    data_lines.append(_row("**All**", n, data_totals))
    print("Every value of every record, the record's provenance and audit included:\n")
    print("\n".join(lines))
    print("\nThe record's data alone (provenance and audit left out):\n")
    print("\n".join(data_lines))
    print("\nExceptional Values in the sample: " + (", ".join(f"{evs[c]} {c}" for c in EV_CLASSES if evs[c]) or "none"))
    return 0


def _row(title, records, c):
    total = sum(c[k] for k in VALUE_CLASSES)
    pct = lambda k: f"{c[k]} ({100 * c[k] / total:.1f}%)" if total else "0"   # noqa: E731
    return f"| {title} | {records} | {total} | " + " | ".join(pct(k) for k in VALUE_CLASSES) + " |"


if __name__ == "__main__":
    sys.exit(main())
