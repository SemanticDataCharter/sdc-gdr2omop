"""The FAIR Data Demo's NHANES Medication model as OMOP CDM 5.4 rows.

Each record is one prescription medicine a respondent took in the past month: a DRUG_EXPOSURE row with the drug's
NHANES generic drug code (Multum Lexicon) as its source value, and a CONDITION_OCCURRENCE row for each reason given,
its ICD-10-CM code looked up in the user's vocabulary and mapped to the standard concept. OMOP's vocabularies carry no
Multum codes, so the drug's concept is 0 and the code travels as text.
"""
from common import OMIT, RECORD_CLUSTERS, C, T, V, person

TITLE = "NHANES Medication (FAIR Data Demo) to OMOP CDM 5.4"
ID = "nhanes-medication-omop-5.4"
VERSION = 1
AUTHOR = "Axius SDC, Inc."
DATE = "2026-10-25"
DESCRIPTION = ("The NHANES Medication model's values as OMOP CDM 5.4 rows. The concepts are the model's own links and "
               "code bindings, looked up in the user's vocabulary; the mapping says which table and column.")

RULES = [
    C("NHANES Medication Governed Record", "."),
    C("NHANES Medication", "."),
    *RECORD_CLUSTERS,
    person(also_period=False),
    T("XdToken", "+OBSERVATION/value_as_concept_id", "answer: an OBSERVATION row"),
    T("XdCount", "+OBSERVATION/value_as_number", "count: an OBSERVATION row"),

    V("Generic Drug Code (RXDDRGID)", "DRUG_EXPOSURE/drug_source_value"),
    OMIT("Generic Drug Name (RXDDRUG)", "DRUG_EXPOSURE has no column for a drug's name; the drug is its source code"),
    V("Diagnosis Code (ICD-10-CM)", "+CONDITION_OCCURRENCE/condition_source_value"),
    OMIT("Code Display Text", "OMOP keeps no display text: a concept's name is the vocabulary's"),
    OMIT("Code System: ICD-10-CM", "the code system is the vocabulary the condition's code is looked up in"),
]
