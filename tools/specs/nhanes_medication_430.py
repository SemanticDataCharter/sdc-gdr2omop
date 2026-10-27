"""The FAIR Data Demo's NHANES Medication 4.3.0 model as OMOP CDM 5.4 rows.

The 4.3.0 model adds NHANES's prevention reason codes as a coded value of their own, beside the ICD-10-CM diagnosis
(FAIR SOURCE-ERRATA.md): `I21.P` is "Prevent heart attack", not an ICD-10-CM code. A prevention reason is not a
condition the participant has, so it is an OBSERVATION row with no standard concept: the NHANES code is the source
value and NHANES's description the value as text. It is never looked up as ICD-10-CM. A drug name, days taken or
reason that was unknown, refused or not known is an Exceptional Value (UNK, ASKR, ASKU), carried as its code, never as
a value.
"""
from common import OMIT, V
from nhanes_medication import RULES as _RULES

TITLE = "NHANES Medication 4.3.0 (FAIR Data Demo) to OMOP CDM 5.4"
ID = "nhanes-medication-4.3.0-omop-5.4"
VERSION = 1
AUTHOR = "Axius SDC, Inc."
DATE = "2026-10-27"
DESCRIPTION = ("The NHANES Medication 4.3.0 model's values as OMOP CDM 5.4 rows. The concepts are the model's own links and "
               "code bindings, looked up in the user's vocabulary; NHANES's prevention reason codes are not ICD-10-CM and get "
               "no concept.")

PREVENTION = ["Prevention Reason (NHANES)"]
RULES = [
    *_RULES[:-2],
    V("Prevention Reason Code (NHANES)", "OBSERVATION/observation_source_value", within=PREVENTION),   # one row with its description
    V("Code Display Text", "OBSERVATION/value_as_string", within=PREVENTION),
    OMIT("Code Display Text", "OMOP keeps no display text: a concept's name is the vocabulary's"),
    OMIT("Code System: NHANES Prevention Reason", "a code system OMOP's vocabularies do not carry: the code has no concept",
         within=PREVENTION),
    OMIT("Code System: ICD-10-CM", "the code system is the vocabulary the condition's code is looked up in"),
]
