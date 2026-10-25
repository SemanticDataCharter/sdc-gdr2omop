"""The FAIR Data Demo's NHANES Participant model as OMOP CDM 5.4 rows.

Quantities are MEASUREMENT rows, answers and counts OBSERVATION rows, each with the concept the component links to
(LOINC for the vital signs and laboratory results, SNOMED CT for the condition questions) and the answer's own code
as value_as_concept_id. The person's gender, race, ethnicity and year of birth go to PERSON through declared tables to
OMOP's Gender, Race and Ethnicity vocabularies. The survey's design is not a person's data, and OMOP has no table for
it.
"""
from common import C, OMIT, OMIT_C, RECORD_CLUSTERS, T, V, person

TITLE = "NHANES Participant (FAIR Data Demo) to OMOP CDM 5.4"
ID = "nhanes-participant-omop-5.4"
VERSION = 1
AUTHOR = "Axius SDC, Inc."
DATE = "2026-10-25"
DESCRIPTION = ("The NHANES Participant model's values as OMOP CDM 5.4 rows. The concepts are the model's own links and "
               "code bindings, looked up in the user's vocabulary; the mapping says which table and column.")

#: OMOP's Race vocabulary codes for the race answers it has a code for.
RACE = {"American Indian or Alaska Native": "Race:1", "Asian or Asian American": "Race:2",
        "Black or African American": "Race:3", "Native Hawaiian or Other Pacific Islander": "Race:4", "White": "Race:5"}
ETHNICITY = {"Mexican American": "Ethnicity:Hispanic", "Other Hispanic": "Ethnicity:Hispanic",
             "Non-Hispanic White": "Ethnicity:Not Hispanic", "Non-Hispanic Black": "Ethnicity:Not Hispanic",
             "Non-Hispanic Asian": "Ethnicity:Not Hispanic", "Other Race - Including Multi-Racial": "Ethnicity:Not Hispanic"}
GENDER = {"male": "Gender:M", "female": "Gender:F"}
#: Age in years at screening, 2017: the year of birth (NHANES top-codes age at 80).
YEAR_OF_BIRTH = {str(age): str(2017 - age) for age in range(0, 81)}

SURVEY_DESIGN = "the survey's design describes the sample, not the person; OMOP CDM has no table for it"

RULES = [
    C("NHANES Participant Governed Record", "."),
    C("NHANES Participant", "."),
    *RECORD_CLUSTERS,
    person(also_period=True),

    # the types' defaults: a quantity is a measurement, an answer or a count an observation
    T("XdQuantity", "+MEASUREMENT/value_as_number", "quantity: a MEASUREMENT row"),
    T("XdToken", "+OBSERVATION/value_as_concept_id", "answer: an OBSERVATION row"),
    T("XdCount", "+OBSERVATION/value_as_number", "count: an OBSERVATION row"),
    V("Ratio of Family Income to Poverty (INDFMPIR)", "+OBSERVATION/value_as_number"),

    # PERSON
    V("Administrative Gender", "PERSON/gender_concept_id", "code", table=GENDER, on_miss="omit",
      also=[{"to": "PERSON/gender_source_value", "transform": "copy"}]),
    OMIT("Gender (RIAGENDR)", "PERSON holds one gender, and Administrative Gender is it"),
    V("Race/Ethnicity Self-Identification", "PERSON/race_concept_id", "code", table=RACE, on_miss="omit",
      also=[{"to": "PERSON/race_source_value", "transform": "copy"}]),
    V("Race/Hispanic Origin with NH Asian (RIDRETH3)", "PERSON/ethnicity_concept_id", "code", table=ETHNICITY,
      also=[{"to": "PERSON/ethnicity_source_value", "transform": "copy"}]),
    V("Age", "PERSON/year_of_birth", "code", table=YEAR_OF_BIRTH),

    # blood pressure: one MEASUREMENT row per reading's value; the reading's other parts have no column
    OMIT_C("Body Site (SNOMED CT)", "OMOP CDM 5.4 MEASUREMENT has no body site column"),
    OMIT("Observation Status", "OMOP CDM has no status for a measurement: a row is a final result"),
    OMIT("Observation Date Time", "rows take the record's date; a reading's own time has no row of its own"),

    # the survey's design
    *[OMIT(label, SURVEY_DESIGN) for label in (
        "Data Release Cycle (SDDSRVYR)", "Interview/Examination Status (RIDSTATR)", "Masked Variance Pseudo-PSU (SDMVPSU)",
        "Masked Variance Pseudo-Stratum (SDMVSTRA)", "Full Sample 2 Year Interview Weight (WTINT2YR)",
        "Full Sample 2 Year MEC Exam Weight (WTMEC2YR)")],
]
