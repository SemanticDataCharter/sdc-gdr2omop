"""What the model's links and code bindings name, as OMOP vocabulary codes.

A component links to the concept it measures or asks (skos:exactMatch to a LOINC code, dc:subject to a SNOMED CT
concept); an enumerated value is defined by a code (rdfs:isDefinedBy to a LOINC answer, a SNOMED CT or NCI Thesaurus
concept); a quantity's unit is a UCUM symbol. Each names a code in a vocabulary OMOP carries, so the concept_id is a
lookup in the user's vocabulary, not a choice in the mapping file.
"""
from __future__ import annotations

import re

#: (pattern, OMOP vocabulary_id). The code is the pattern's first group.
PATTERNS = [
    (re.compile(r"^https?://loinc\.org/(?:rdf/)?([0-9]+-[0-9]|LA[0-9]+-[0-9]|LP[0-9]+-[0-9])/?$"), "LOINC"),
    (re.compile(r"^https?://snomed\.info/(?:id|sct)/([0-9]+)/?$"), "SNOMED"),
    (re.compile(r"^https?://purl\.obolibrary\.org/obo/NCIT_(C[0-9]+)$"), "NCIt"),
]
#: Code systems a component can name for the codes its value holds (the value is the code).
CODE_SYSTEMS = {
    "http://hl7.org/fhir/sid/icd-10-cm": "ICD10CM",
    "http://hl7.org/fhir/sid/icd-10": "ICD10",
    "http://snomed.info/sct": "SNOMED",
    "http://loinc.org": "LOINC",
    "http://www.nlm.nih.gov/research/umls/rxnorm": "RxNorm",
}
EXACT = "http://www.w3.org/2004/02/skos/core#exactMatch"
SUBJECT = "http://purl.org/dc/terms/subject"
SOURCE = "http://purl.org/dc/terms/source"


def code_of(iri: str | None) -> tuple[str, str] | None:
    """(vocabulary_id, concept_code) an IRI names, or None."""
    if not iri:
        return None
    for pattern, vocabulary in PATTERNS:
        m = pattern.match(iri.strip())
        if m:
            return vocabulary, m.group(1)
    return None


def concept_of(links: dict[str, list[str]]) -> tuple[str, str] | None:
    """The concept a component measures or asks: its exact match, else its subject."""
    for predicate in (EXACT, SUBJECT):
        for iri in links.get(predicate, []):
            found = code_of(iri)
            if found:
                return found
    return None


def code_system_of(links: dict[str, list[str]]) -> str | None:
    """The vocabulary of the codes a component's value holds, where the component names one."""
    for predicate in (EXACT, SOURCE):
        for iri in links.get(predicate, []):
            if iri.rstrip("/") in CODE_SYSTEMS:
                return CODE_SYSTEMS[iri.rstrip("/")]
    return None
