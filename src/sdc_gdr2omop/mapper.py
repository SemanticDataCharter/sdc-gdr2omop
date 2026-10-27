"""The OMOP CDM 5.4 mapper: a Governed Data Record as rows of the OMOP Common Data Model.

The mapping file says which table and column each value goes to (`+MEASUREMENT/value_as_number`: a row of its own in
MEASUREMENT; `PERSON/gender_concept_id`: the record's one PERSON row; `RECORD/person_id` and `RECORD/event_date`: what
every row of the record takes). The concept for each row comes from the model, not the mapping: the component's link
to the concept it measures or asks (a LOINC code, a SNOMED CT concept), the code an enumerated value is defined by,
the code system a component names for the codes it holds (ICD-10-CM), the UCUM symbol of a unit. Each is looked up in
the user's vocabulary (an Athena download), and a value whose concept comes from the model is a lookup; one the
mapping places without a concept from the model is declared; one written only as a source value, with no vocabulary
OMOP carries to look it up in, is carried.

OMOP's own conventions the writer applies: a NOT NULL concept column with no concept is 0 ("No matching concept");
the component's identifier is the row's *_source_value when the value is not itself a code; every row of the record
takes its person and its date from RECORD; a drug exposure with no end date ends when it starts; ids are sequences
per mapper instance (a loader assigns final ids).
"""
from __future__ import annotations

from dataclasses import dataclass

from sdc_mapper import (CARRIED, DECLARED, EV_CARRIED, LOOKUP, LOST, NOT_REPRESENTABLE, EVRule, IncompleteMapping,
                        MapResult, MappingError, ValueOutcome, place)
from sdcreader.record import EXCEPTIONAL_VALUES

from . import __version__
from .iri import code_system_of, concept_of, vocabulary_code
from .vocabulary import Vocabulary
from .writer import Row, columns, load, to_csv

CANNOT_HOLD = [
    "the record's provenance and audit clusters",
    "validity windows and the time a value was recorded (act, vtb, vte, tr)",
    "a survey's design: its weights, strata, primary sampling units and release",
    "why a value is missing beyond its ISO 21090 code as text: OMOP has no column for an Exceptional Value",
]


@dataclass(frozen=True)
class Event:
    """An OMOP event table's conventional columns."""
    concept: str
    date: str
    type: str
    source: str
    source_concept: str
    end_date: str | None = None


EVENTS = {
    "measurement": Event("measurement_concept_id", "measurement_date", "measurement_type_concept_id",
                         "measurement_source_value", "measurement_source_concept_id"),
    "observation": Event("observation_concept_id", "observation_date", "observation_type_concept_id",
                         "observation_source_value", "observation_source_concept_id"),
    "condition_occurrence": Event("condition_concept_id", "condition_start_date", "condition_type_concept_id",
                                  "condition_source_value", "condition_source_concept_id"),
    "drug_exposure": Event("drug_concept_id", "drug_exposure_start_date", "drug_type_concept_id",
                           "drug_source_value", "drug_source_concept_id", end_date="drug_exposure_end_date"),
}
RECORD_COLUMNS = {"person_id", "event_date"}


def _own(key) -> bool:
    return isinstance(key, tuple) and bool(key) and isinstance(key[-1], tuple) and key[-1][:1] == ("+",)


def _source_column(table: str, column: str) -> str | None:
    """Where the text of a value goes when OMOP has a concept column for it but no concept: its source column."""
    if column in ("value_as_number", "value_as_concept_id"):
        return "value_source_value"
    event = EVENTS.get(table)
    if event and column == event.source:
        return column
    if column.endswith("_concept_id"):
        candidate = column.removesuffix("_concept_id") + "_source_value"
        if candidate in {c.name for c in columns(table)}:
            return candidate
    return None


class OMOPMapper:
    name = "omop"
    target = "OMOP CDM"
    target_version = "5.4"
    package = "sdc-gdr2omop"
    version = __version__
    #: OMOP has no column for why a value is missing: the ISO 21090 code is carried as the value's source text.
    ev_table = {code: EVRule(EV_CARRIED, target_code=code) for code in EXCEPTIONAL_VALUES}

    def __init__(self, vocabulary: Vocabulary | str | None = None):
        self.vocabulary = vocabulary if isinstance(vocabulary, Vocabulary) else Vocabulary(vocabulary)
        self.sequences: dict[str, int] = {}

    # ------------------------------------------------------------ the call
    def map(self, record, mapping) -> MapResult:
        if mapping is None:
            raise MappingError("OMOP needs a mapping file: the model does not say which table each value goes to")
        if mapping.carry_rejected:
            raise MappingError("carry_rejected is not available: a rejected value never becomes a row")
        for code, override in mapping.exceptional_values.items():
            if override["class"] not in (EV_CARRIED, LOST):
                raise MappingError(f"OMOP cannot preserve {code}: it has no null flavors, only a source value to "
                                   "carry the code in")
        self._evs = {**self.ev_table, **{code: EVRule(o["class"], o.get("target_code", ""))
                                         for code, o in mapping.exceptional_values.items()}}
        placements, _ = place(record, mapping)
        self._record: dict[str, str] = {}
        self._rows: dict[tuple, Row] = {}
        self._exceptional_at: set[int] = set()         # positions of the record's Exceptional Values
        outcomes: dict[int, ValueOutcome] = {}
        missing = []

        # what every row of the record takes (its person, its date) before any row
        ordered = sorted(placements, key=lambda p: 0 if p.steps and p.steps[0][0].upper() == "RECORD" else 1)
        for p in ordered:
            v = p.value
            if p.omitted:
                if v.exceptional:               # an Exceptional Value has an EV outcome: where its value cannot go, it is lost
                    self._exceptional_at.add(v.position)
                    outcomes[v.position] = ValueOutcome(v.position, LOST, note=f"{v.exceptional.code}: the component is not "
                                                        f"mapped ({p.omitted_by.reason or 'omitted'})")
                    continue
                outcomes[v.position] = ValueOutcome(v.position, NOT_REPRESENTABLE, note=p.omitted_by.reason or "")
                continue
            if p.rule is None:
                missing.append(f"{' / '.join(v.path_labels + [v.label])} ({v.ct_id})")
                continue
            table, key, column = self._target(p.steps)
            if v.exceptional:
                self._exceptional_at.add(v.position)
                outcomes[v.position] = self._exceptional(p, table, key, column)
                continue
            carried_to = None
            for e in p.extras:
                if e.text is not None:
                    t, k, c = self._target(e.steps)
                    self._write(t, k, c, e.text, position=v.position if p.text is None else None)
                    carried_to = carried_to or f"{t.upper()}.{c}"
            if p.text is None:              # a code table without the value: carried, when a source column holds it
                outcomes[v.position] = (ValueOutcome(v.position, CARRIED, location=carried_to, note=p.note)
                                        if carried_to else
                                        ValueOutcome(v.position, NOT_REPRESENTABLE, note=p.note or "no value to write"))
                continue
            cls = self._value(p, table, key, column)
            outcomes[v.position] = ValueOutcome(v.position, cls, location=f"{table.upper()}.{column}")
        if missing:
            raise IncompleteMapping(f"mapping {mapping.id} has no rule for {len(missing)} value(s): " + "; ".join(missing[:5]))

        rows = self._finish(outcomes)
        files = to_csv(rows)
        load(files)                                          # the OHDSI DDL's types, NOT NULLs and keys
        return MapResult(files=files, outcomes=[outcomes[v.position] for v in record.values],
                         cannot_hold=list(CANNOT_HOLD))

    # ------------------------------------------------------------ placing values
    @staticmethod
    def _target(steps):
        if len(steps) != 2:
            raise MappingError(f"an OMOP path is TABLE/column: {'/'.join(n for n, _ in steps)}")
        (table, key), (column, _) = steps
        return table.lower(), key, column

    def _row(self, table: str, key) -> Row:
        k = (table, key) if _own(key) else (table, "record")
        if k not in self._rows:
            columns(table)
            self._rows[k] = Row(table)
        return self._rows[k]

    def _write(self, table, key, column, text, position=None):
        if table == "record":
            if column not in RECORD_COLUMNS:
                raise MappingError(f"RECORD has {sorted(RECORD_COLUMNS)}, not {column!r}")
            self._record.setdefault(column, text)
            return None
        row = self._row(table, key)
        row.set(column, text, position=position)
        return row

    def _value(self, p, table, key, column) -> str:
        v = p.value
        if table == "record":
            self._write(table, key, column, p.text)
            return DECLARED
        row = self._row(table, key)
        voc = self.vocabulary
        event = EVENTS.get(table)
        looked_up = carried = False
        if column == "value_as_concept_id":
            code = vocabulary_code(v.code.defined_by) if v.code else None
            row.set(column, voc.standard(*code) if code else 0, position=v.position)
            self._value_text(row, p.text)
            looked_up = code is not None
        elif column == "value_as_number":
            row.set(column, p.text, position=v.position)
            if v.units:
                row.set("unit_source_value", v.units.symbol)
                row.set("unit_concept_id", voc.standard("UCUM", v.units.symbol))
        elif event and column == event.source:              # the value is a code: its vocabulary is the component's
            row.set(column, p.text, position=v.position)
            vocabulary = code_system_of(v.links)
            if vocabulary:
                row.set(event.source_concept, voc.source(vocabulary, p.text))
                row.set(event.concept, voc.standard(vocabulary, p.text))
                looked_up = True
            else:
                carried = True
        elif column.endswith("_concept_id") and ":" in p.text:   # a code table's "VOCABULARY:code"
            vocabulary, code = p.text.split(":", 1)
            row.set(column, voc.standard(vocabulary, code), position=v.position)
        else:
            row.set(column, p.text, position=v.position)
        if p.attributes:
            for k, val in p.attributes.items():
                row.set(k, val)
        if event and column != event.source:
            looked_up = self._row_concept(row, event, v) or looked_up
        return LOOKUP if looked_up else CARRIED if carried else DECLARED

    @staticmethod
    def _value_text(row: Row, text: str | None):
        """An answer's text: value_source_value when it fits OMOP's 50 characters, else (in OBSERVATION) the
        60-character value_as_string; the answer's concept carries it either way when the model binds one."""
        if text is None:
            return
        if len(text) <= 50:
            row.set("value_source_value", text)
        elif row.table == "observation" and len(text) <= 60:
            row.set("value_as_string", text)

    def _row_concept(self, row: Row, event: Event, v) -> bool:
        """The row's concept: the concept the component measures or asks, from its link; the component's identifier
        as the source value. True when the model gave a concept."""
        if row.values.get(event.concept) not in (None, "0") or row.values.get(event.source):
            return False
        found = concept_of(v.links)
        row.set(event.source, v.ct_id)
        if found:
            row.set(event.source_concept, self.vocabulary.source(*found))
            row.set(event.concept, self.vocabulary.standard(*found))
            return True
        return False

    def _exceptional(self, p, table, key, column) -> ValueOutcome:
        v = p.value
        rule = self._evs[v.exceptional.code]
        source = None if table == "record" else _source_column(table, column)
        if rule.cls == LOST or source is None:
            return ValueOutcome(v.position, LOST, note=f"OMOP {table.upper()}.{column} has no source column for "
                                                       f"{v.exceptional.code}" if source is None else "")
        row = self._row(table, key)
        row.set(source, v.exceptional.code, position=v.position)
        event = EVENTS.get(table)
        if event and column != event.source:
            self._row_concept(row, event, v)
        return ValueOutcome(v.position, EV_CARRIED, location=f"{table.upper()}.{source}", target_code=v.exceptional.code)

    # ------------------------------------------------------------ OMOP's conventions, then the rows
    def _finish(self, outcomes: dict[int, ValueOutcome]) -> list[Row]:
        person = self._record.get("person_id")
        date = self._record.get("event_date")
        kept = []
        for row in self._rows.values():
            names = {c.name for c in columns(row.table)}
            if "person_id" in names and person is not None:
                row.set("person_id", person, overwrite=True)
            id_column = f"{row.table}_id"
            if id_column in names and id_column != "person_id":
                self.sequences[row.table] = self.sequences.get(row.table, 0) + 1
                row.set(id_column, self.sequences[row.table])
            event = EVENTS.get(row.table)
            if event and date and not row.values.get(event.date):
                row.set(event.date, date)
            if event and event.end_date and not row.values.get(event.end_date):
                row.set(event.end_date, row.values.get(event.date))
            for c in columns(row.table):                     # OMOP: a concept column with no concept is 0
                if c.required and c.name.endswith("_concept_id") and row.values.get(c.name) in (None, ""):
                    row.set(c.name, 0)
            gone = row.missing()
            if gone:
                why = f"OMOP requires {row.table.upper()}.{gone[0]}, and the record has no value for it"
                for pos in row.positions:
                    # an Exceptional Value stays one (by position: a carried value and a carried EV share the class name)
                    outcomes[pos] = ValueOutcome(pos, LOST if pos in self._exceptional_at else NOT_REPRESENTABLE,
                                                 note=why)
                continue
            kept.append(row)
        return kept
