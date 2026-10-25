# Changelog

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
