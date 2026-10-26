"""The FAIR Data Demo's NHANES Participant 4.2.4 model as OMOP CDM 5.4 rows.

The 4.2.4 model is a revision of NHANES Participant 4.2.3 whose value bindings and concept links name codes their
terminologies confirm (E-2026-10-03: some named an unrelated concept, some were shared by values that mean different
things, and the difficulty scale bound every level to Unknown). Where no concept says exactly what a value says, the
value is defined by the agency's codebook, which is not a code: its row has no value concept, only the answer's text.
Labels and structure are the 4.2.0 model's, so the rules are the 4.2.0 spec's.
"""
from nhanes_participant import *  # noqa: F401,F403
from nhanes_participant import RULES  # noqa: F401

TITLE = "NHANES Participant 4.2.4 (FAIR Data Demo) to OMOP CDM 5.4"
ID = "nhanes-participant-4.2.4-omop-5.4"
DATE = "2026-10-26"
DESCRIPTION = ("The NHANES Participant 4.2.4 model's values as OMOP CDM 5.4 rows. The concepts are the model's own links "
               "and code bindings, looked up in the user's vocabulary; the mapping says which table and column.")
