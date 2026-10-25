"""What the model's links and code bindings name, as OMOP vocabulary codes.

A component links to the concept it measures or asks (skos:exactMatch to a LOINC code, dc:subject to a SNOMED CT
concept); an enumerated value is defined by a code (rdfs:isDefinedBy to a LOINC answer, a SNOMED CT or NCI Thesaurus
concept); a quantity's unit is a UCUM symbol. Each names a code in a vocabulary OMOP carries, so the concept_id is a
lookup in the user's vocabulary, not a choice in the mapping file.

Reading the IRIs is sdc-mapper's (`sdc_mapper.codes`, 4.3.0); what is OMOP's here is the name each code system has in
the OMOP vocabularies, and the code systems a component can name for the codes its value holds.
"""
from __future__ import annotations

from sdc_mapper import CONCEPT_LINKS, LOINC, NCIT, SNOMED_CT, code_of

#: The code systems the model names concepts in, by the IRI sdc-mapper names them with, as OMOP vocabulary_ids. A code
#: in any other system (a code list's `#code`) is not one OMOP carries.
VOCABULARIES = {LOINC: "LOINC", SNOMED_CT: "SNOMED", NCIT: "NCIt"}
#: Code systems a component can name for the codes its value holds (the value is the code).
CODE_SYSTEMS = {
    "http://hl7.org/fhir/sid/icd-10-cm": "ICD10CM",
    "http://hl7.org/fhir/sid/icd-10": "ICD10",
    "http://snomed.info/sct": "SNOMED",
    "http://loinc.org": "LOINC",
    "http://www.nlm.nih.gov/research/umls/rxnorm": "RxNorm",
}
EXACT = "http://www.w3.org/2004/02/skos/core#exactMatch"
SOURCE = "http://purl.org/dc/terms/source"


def vocabulary_code(iri: str | None) -> tuple[str, str] | None:
    """(vocabulary_id, concept_code) an IRI names in a vocabulary OMOP carries, or None."""
    ref = code_of(iri)
    if ref is None or ref.system not in VOCABULARIES:
        return None
    return VOCABULARIES[ref.system], ref.code


def concept_of(links: dict[str, list[str]]) -> tuple[str, str] | None:
    """The concept a component measures or asks: its exact match, else its subject."""
    for predicate in CONCEPT_LINKS:
        for iri in links.get(predicate, []):
            found = vocabulary_code(iri)
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
