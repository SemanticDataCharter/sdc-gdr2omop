"""The FAIR Data Demo's NHANES Participant 4.3.1 model as OMOP CDM 5.4 rows.

The 4.3.1 model is a revision of NHANES Participant 4.3.0 whose four NIH CDE answers (race and ethnicity, pregnancy,
education, health insurance) carry their compound concepts as dcterms:subject, with no exact-match claim (NIH CDE
library R-2026-10-27). As in 4.3.0, published under SDCStudio 4.24: an answer the participant
refused or did not know is an Exceptional Value (ASKR, ASKU) in place of the answer. An Exceptional Value is never a
value: it travels as its code in the row's source column, and the row's value concept stays 0. Labels and structure
are the 4.2.0 model's, so the rules are the 4.2.0 spec's.
"""
from nhanes_participant import *  # noqa: F401,F403
from nhanes_participant import RULES  # noqa: F401

TITLE = "NHANES Participant 4.3.1 (FAIR Data Demo) to OMOP CDM 5.4"
ID = "nhanes-participant-4.3.1-omop-5.4"
DATE = "2026-10-27"
DESCRIPTION = ("The NHANES Participant 4.3.1 model's values as OMOP CDM 5.4 rows. The concepts are the model's own links "
               "and code bindings, looked up in the user's vocabulary; the mapping says which table and column.")
