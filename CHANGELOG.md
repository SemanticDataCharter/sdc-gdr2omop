# Changelog

## 4.0.4 (2026-10-26)

- **NHANES Participant 4.2.4** (`tp5pg0u4dasqarie0b3ujn2u`): its mapping, a sample of 200 of its records (the 4.2.3
  sample's participants), and the tests on it beside 4.2.0 and 4.2.3. The FAIR Data Demo's 4.2.4 binds its values to
  codes their terminologies confirm (E-2026-10-03): 4.2.3 bound every level of the difficulty scale to NCIt Unknown,
  both pregnancy-at-exam answers to C25191 (Person Name) and both citizenship answers to C41130 (Significant). For the
  same participants, value_as_concept_id now looks up C121736 to C121742, C82475 Not Pregnant and C90516 Citizen.
- A value 4.2.4 defines by an agency codebook page (no concept says exactly what it says: "Not a citizen of the US",
  "Less than 9th grade", "Do not do this activity") has value_as_concept_id 0 and its text as value_source_value; no
  cell names the codebook or the variable its anchor points at. A test holds both.
- The 4.2.0 and 4.2.3 mappings stay: both models are retired, and records made on them still exist.

## 4.0.3 (2026-10-25)

- **NHANES Participant 4.2.3** (`eehpfapwgvxtzdrofgstdcfs`): its mapping, a seeded sample of 200 of its records, and
  the tests run on it and on 4.2.0. The FAIR Data Demo's 4.2.3 model composes the NIH CDE library's corrected "Are you
  pregnant now?" (E-2026-10-01: NIH's record bound each answer to the next value's LOINC code), so an answer's
  value_as_concept_id is now the right one: Yes is LA15173-0 (Pregnant), No LA26683-5, Unknown LA4489-6. The 4.2.0
  mapping stays, for records made on that model.
- **Fix:** a person lost to an exceptional birth year turned a value carried as source text (a race OMOP has no code
  for) into a lost Exceptional Value, and the record was refused as an incomplete mapping. CARRIED and EV_CARRIED are
  the same word in sdc-mapper; the mapper now tells an Exceptional Value by its position.

## 4.0.2 (2026-10-25)

Uses sdc-mapper 4.3.0's code reading (`sdc_mapper.codes`) for the IRIs a model names concepts with (LOINC, SNOMED CT,
NCI Thesaurus); the mapper keeps only what is OMOP's: each code system's OMOP vocabulary_id, and the code systems a
component can name for the codes its value holds. No change to any output: every sample record maps to the same files
and the same report, byte for byte. Requires sdc-mapper 4.3.

## 4.0.1 (2026-10-25)

Rebuilt with the release job's pip pinned by hash: CI and the release workflow install pip 26.2.2 from a hash-pinned
wheel before anything else is fetched (the eMudhra/emSign CA compromise: pip before 26.2.2 trusts the compromised root
through its vendored certifi). No change to the package.

## 4.0.0 (2026-10-25)

The health mapper of the sdc-mapper line: Governed Data Records as OMOP CDM 5.4 rows.

- **The mapper**: one CSV per OMOP table, the DDL's columns in order; every row's concept from the model (the
  component's link, the value's code binding, the unit's UCUM symbol, the code system a component names), looked up in
  the user's Athena vocabulary and followed through "Maps to"; OMOP's conventions for concept 0, source values, the
  record's person and date; ids as sequences per mapper.
- **Every call's rows are loaded** into an in-memory DuckDB database built from OHDSI's 5.4 DDL and primary keys
  (shipped unmodified); a row the DDL refuses fails the call.
- **The NHANES Participant and NHANES Medication mappings** for the FAIR Data Demo, written by `tools/build_mapping.py`
  from specs in the model's labels. Dates, year of birth, gender, race and ethnicity are declared where NHANES does not
  say them.
- **Exceptional Values are carried** as the row's source value; lost where the column has none.
- **`tools/measure.py`**: the coverage of the sample, as in the README.
