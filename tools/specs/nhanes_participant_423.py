"""The FAIR Data Demo's NHANES Participant 4.2.3 model as OMOP CDM 5.4 rows.

The 4.2.3 model is a revision of NHANES Participant (4.2.0) that composes the NIH CDE library's corrected "Are you
pregnant now?" (E-2026-10-01: NIH's record bound each answer to the next value's LOINC code). Everything else is the
same model, so the rules are the 4.2.0 spec's.
"""
from nhanes_participant import *  # noqa: F401,F403
from nhanes_participant import RULES  # noqa: F401

TITLE = "NHANES Participant 4.2.3 (FAIR Data Demo) to OMOP CDM 5.4"
ID = "nhanes-participant-4.2.3-omop-5.4"
DESCRIPTION = ("The NHANES Participant 4.2.3 model's values as OMOP CDM 5.4 rows. The concepts are the model's own links "
               "and code bindings, looked up in the user's vocabulary; the mapping says which table and column.")
