"""The user's OMOP vocabulary, read from an Athena download: CONCEPT.csv and CONCEPT_RELATIONSHIP.csv.

This package never ships a vocabulary. Athena's vocabularies come under their own licenses, some of which require the
user's own agreement (CPT4, for one), so the user downloads them and gives the directory at run time. Without one,
every concept_id is 0 (OMOP's "No matching concept") and the source code stays in the *_source_value column.
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path

ENV = "SDC_OMOP_VOCABULARY"


@dataclass(frozen=True)
class Concept:
    concept_id: int
    standard: bool


class Vocabulary:
    def __init__(self, directory: str | Path | None = None):
        directory = directory or os.environ.get(ENV)
        self.directory = Path(directory) if directory else None
        self.concepts: dict[tuple[str, str], Concept] = {}
        self.maps_to: dict[int, int] = {}
        if self.directory is None:
            return
        csv.field_size_limit(10_000_000)
        with open(self.directory / "CONCEPT.csv", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                self.concepts[(row["vocabulary_id"], row["concept_code"])] = Concept(
                    int(row["concept_id"]), row.get("standard_concept") == "S")
        with open(self.directory / "CONCEPT_RELATIONSHIP.csv", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                if row["relationship_id"] == "Maps to" and not row.get("invalid_reason"):
                    self.maps_to.setdefault(int(row["concept_id_1"]), int(row["concept_id_2"]))

    @property
    def present(self) -> bool:
        return self.directory is not None

    def source(self, vocabulary: str, code: str) -> int:
        """The concept for a code as the source wrote it (standard or not); 0 when the vocabulary lacks it."""
        c = self.concepts.get((vocabulary, code))
        return c.concept_id if c else 0

    def standard(self, vocabulary: str, code: str) -> int:
        """The standard concept for a code: itself when standard, else where it 'Maps to'; 0 when there is none."""
        c = self.concepts.get((vocabulary, code))
        if c is None:
            return 0
        return c.concept_id if c.standard else self.maps_to.get(c.concept_id, 0)
