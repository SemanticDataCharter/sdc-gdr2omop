# sdc-gdr2omop

Governed Data Records as rows of the OMOP Common Data Model 5.4. A target mapper for
[sdc-mapper](https://github.com/SemanticDataCharter/sdc-mapper): the core validates the record, resolves every value
against its model and reports each one; this package says which OMOP table and column each value goes to, takes each
row's concept from the model, and writes one CSV per table. Outbound only. Apache 2.0.

**Status:** 4.0.5. Models so far, from the [FAIR Data Demo](https://github.com/SemanticDataCharter/FAIR_Data_Demo):
**NHANES Participant 4.3.0** (`drjvqb171q9pqwcdq6nxxrr4`) and **NHANES Medication 4.3.0** (`plc9gto1kzy244g1r2op257f`),
and the retired models whose records still exist: NHANES Participant 4.2.4 (`tp5pg0u4dasqarie0b3ujn2u`), 4.2.3
(`eehpfapwgvxtzdrofgstdcfs`) and 4.2.0 (`xy8upneajsb8vdcmnve01g6g`), and NHANES Medication 4.2.0
(`epbdfmvxc3gbh5f66hhb3o2m`). 4.3.0 carries a refused or unknown answer as an Exceptional Value in place of the answer,
and NHANES's prevention reason codes (`I21.P`, prevent heart attack) as a code system of their own, not ICD-10-CM (the
FAIR Data Demo's `SOURCE-ERRATA.md`). NHANES Participant 4.2.3 composes the NIH CDE library's corrected "Are you
pregnant now?" (E-2026-10-01); 4.2.4 binds its values to codes their terminologies confirm (E-2026-10-03). A value no
concept says exactly is defined by the agency's codebook, which is not a code: its row has value_as_concept_id 0 and
the answer as value_source_value. Each mapping writes the codes its model binds.

## Use

```python
from sdc_mapper import Engine, load_mapping
from sdc_gdr2omop import OMOPMapper, mapping_path

mapper = OMOPMapper("/path/to/athena")         # or SDC_OMOP_VOCABULARY; without one, every concept_id is 0
result = Engine().map_record(xml, mapper, load_mapping(mapping_path("drjvqb171q9pqwcdq6nxxrr4")))
result.files            # {"person.csv": ..., "measurement.csv": ..., ...}, the DDL's columns in order
result.report           # every value: lookup, declared, carried or not representable, and why
```

Through sdc-mapper's CLI and MCP server the mapper is the target `omop`. Use one mapper for a stream: its row ids are
sequences per mapper, so the rows of many records load into one database without colliding. A loader that merges
streams assigns final ids.

## The target and its terms

**OMOP Common Data Model 5.4**, from OHDSI's CommonDataModel repository (tag v5.5.0, `inst/ddl/5.4/duckdb`), licensed
Apache License 2.0. This package carries the DuckDB DDL and primary keys unmodified (see `NOTICE`), and every call
loads its rows into an in-memory DuckDB database built from them: a value of the wrong type, a missing NOT NULL column
or a duplicate key fails the load and the call.

**Vocabularies are never shipped.** OMOP's standardized vocabularies come from Athena (https://athena.ohdsi.org),
each under its own terms, shown when they are downloaded; some need a license of the user's own. The user gives the
directory of their download (CONCEPT.csv, CONCEPT_RELATIONSHIP.csv) at run time. Without one, every concept_id is 0,
OMOP's "No matching concept", and the source code stays in the row's source value. The tests use a made-up vocabulary
(`tests/vocabulary-made-up/`), labeled as such, with concept ids no vocabulary uses.

## Where values go, and where the concepts come from

A mapping file, one per model (`src/sdc_gdr2omop/mappings/`), says which table and column each value goes to:
`+MEASUREMENT/value_as_number` (a row of its own), `PERSON/gender_concept_id` (the record's one PERSON row),
`RECORD/person_id` and `RECORD/event_date` (what every row of the record takes). Defaults by type keep it short: a
quantity is a MEASUREMENT row, an answer or a count an OBSERVATION row.

The concepts come from the model, not the mapping:

- the row's concept is the one the component links to: a LOINC code for each vital sign and laboratory result, a SNOMED
  CT concept for each condition question;
- an answer's value_as_concept_id is the code its enumerated value is defined by (a LOINC answer, a SNOMED CT or NCI
  Thesaurus concept);
- a unit is its UCUM symbol;
- a value that is itself a code is looked up in the code system the component names (ICD-10-CM) and followed through
  "Maps to" to its standard concept.

Each is looked up in the user's vocabulary. A value whose concept comes from the model is a **lookup**; one the mapping
places without a concept from the model is **declared**; one written only as source text, with no vocabulary OMOP
carries, is **carried**.

What the mapping declares, because NHANES does not say it:

- **Dates.** NHANES publishes no exam or interview dates. Every row of a 2017-2018 record takes the cycle's first day,
  2017-01-01, and each person's observation period is the cycle (2017-01-01 to 2018-12-31).
- **Year of birth** is 2017 less the age at screening, by a table in the mapping (NHANES top-codes age at 80).
- **Gender, race and ethnicity** go to OMOP's Gender, Race and Ethnicity vocabularies by tables in the mapping. Two
  race answers have no code in OMOP's Race vocabulary ("Hispanic, Latino, or Spanish"; "Middle Eastern or North
  African"): the concept is 0 and the answer is carried as race_source_value.

OMOP's conventions the mapper applies: a NOT NULL concept column with no concept is 0; type concepts are 0, for a
site to set in its own profile of the mapping; the component's identifier is the row's source value when the value is
not itself a code; a drug exposure with no end date ends the day it starts.

## Coverage, measured

`python tools/measure.py` maps every sample record (200 of each model, a seeded sample of the FAIR Data Demo's
NHANES 2017-2018 records) and counts each value's class. Lookups here mean the model names the concept; whether the
user's vocabulary holds each code is the vocabulary's.

Every value of every record, the record's provenance and audit included:

| Model | Records | Values | Lookup | Declared | Carried | Not representable |
|---|---|---|---|---|---|---|
| NHANES Participant | 200 | 19226 | 9045 (47.0%) | 2023 (10.5%) | 44 (0.2%) | 8114 (42.2%) |
| NHANES Participant 4.2.3 | 200 | 19235 | 9051 (47.1%) | 2041 (10.6%) | 50 (0.3%) | 8093 (42.1%) |
| NHANES Participant 4.2.4 | 200 | 19235 | 9026 (46.9%) | 2066 (10.7%) | 50 (0.3%) | 8093 (42.1%) |
| NHANES Participant 4.3.0 | 200 | 19247 | 9026 (46.9%) | 2066 (10.7%) | 62 (0.3%) | 8093 (42.0%) |
| NHANES Medication | 200 | 6991 | 400 (5.7%) | 591 (8.5%) | 200 (2.9%) | 5800 (83.0%) |
| NHANES Medication 4.3.0 | 200 | 6997 | 394 (5.6%) | 601 (8.6%) | 212 (3.0%) | 5790 (82.7%) |
| **All** | 1200 | 90931 | 36942 (40.6%) | 9388 (10.3%) | 618 (0.7%) | 43983 (48.4%) |

The record's data alone (provenance and audit left out):

| Model | Records | Values | Lookup | Declared | Carried | Not representable |
|---|---|---|---|---|---|---|
| NHANES Participant | 200 | 13826 | 9045 (65.4%) | 2023 (14.6%) | 44 (0.3%) | 2714 (19.6%) |
| NHANES Participant 4.2.3 | 200 | 13835 | 9051 (65.4%) | 2041 (14.8%) | 50 (0.4%) | 2693 (19.5%) |
| NHANES Participant 4.2.4 | 200 | 13835 | 9026 (65.2%) | 2066 (14.9%) | 50 (0.4%) | 2693 (19.5%) |
| NHANES Participant 4.3.0 | 200 | 13847 | 9026 (65.2%) | 2066 (14.9%) | 62 (0.4%) | 2693 (19.4%) |
| NHANES Medication | 200 | 1591 | 400 (25.1%) | 591 (37.1%) | 200 (12.6%) | 400 (25.1%) |
| NHANES Medication 4.3.0 | 200 | 1597 | 394 (24.7%) | 601 (37.6%) | 212 (13.3%) | 390 (24.4%) |
| **All** | 1200 | 58531 | 36942 (63.1%) | 9388 (16.0%) | 618 (1.1%) | 11583 (19.8%) |

What OMOP cannot hold here: the record's provenance and audit; the survey's design (weights, strata, primary sampling
units, release, interview status), which describes the sample rather than the person; a blood pressure reading's body
site and status (MEASUREMENT has no column for either); a second statement of gender (PERSON holds one); a drug's name
and a diagnosis code's display text (OMOP keeps the code; the name is the vocabulary's). The NHANES generic drug codes
are Multum Lexicon codes, which OMOP's vocabularies do not carry, so each drug exposure's concept is 0 and its code is
carried.

## Exceptional Values

OMOP has no null flavors and no column that says why a value is missing; concept 0 means "No matching concept", not a
reason. So every ISO 21090 code is **carried**: the code is written as the row's source value for the column the value
would have filled (value_source_value for a measurement or an answer, gender_source_value for gender, the code column
itself for a value that is a code), beside the row's concept. Where the column has no source value (year_of_birth, a
date), the Exceptional Value is **lost**, and where OMOP requires that column the row cannot be written: every value
in it is reported as not representable, with the reason (`OMOP requires PERSON.year_of_birth, and the record has no
value for it`). A mapping file may declare a code lost; it cannot declare one preserved.

The two NHANES Participant samples are separate seeded draws of 200 participants, so their counts differ by who was
drawn; the mappings place every value the same way.

The 4.3.0 samples hold Exceptional Values: a participant's refused or don't-know answer is ASKR or ASKU, and a drug name,
days taken or reason that NHANES records as unknown, refused or not known is UNK, ASKR or ASKU. An answer's is carried
as its code (its value_source_value is `ASKR`, never a value). Where the Exceptional Value stands in place of the code
that makes a row a clinical fact (a medication reason's ICD-10-CM code: CONDITION_OCCURRENCE; likewise a drug,
procedure or measurement code), there is no fact to record: no row is written, and the Exceptional Value is **lost**,
with the reason in the report ("OMOP has no condition to record for a code that is ASKU"). A row with concept 0 and
`ASKU` as its source value would be counted as a recorded condition. A component the mapping does not map (a drug's
name) has nowhere to carry its Exceptional Value either, so it is lost, and the record still maps. The earlier samples hold none: the FAIR
Data Demo left refusals out before 4.3.0.

## NHANES's prevention reason codes

NHANES writes a reason a medicine is taken to prevent a condition as the condition's ICD-10-CM code with "P" appended
(`I21.P`, prevent heart attack). No such code is in ICD-10-CM, and the condition is one the participant is preventing,
not one diagnosed. NHANES Medication 4.3.0 carries these as their own coded value, and this mapper writes each as an
OBSERVATION row with no concept (observation_concept_id 0): the NHANES code is its observation_source_value and
NHANES's description its value_as_string. It is never a CONDITION_OCCURRENCE and never looked up as ICD-10-CM, even
in a vocabulary that has a concept with that code (a test makes sure).

## Tests

```
pip install -e ".[dev]"
python -m pytest
```

The suite maps every sample record and loads them into a CDM built from the OHDSI DDL (one per participant model: the
two samples share participants), checks lookups
against the made-up vocabulary (the pregnancy answers among them, on both models), and exercises Exceptional Values and refused mappings.
