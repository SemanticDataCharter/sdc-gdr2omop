"""NHANES records as OMOP CDM 5.4 rows: every value accounted for, every row loaded into a CDM built from the OHDSI
DDL, concepts from the model looked up in the user's vocabulary (here a made-up one), Exceptional Values carried."""
from __future__ import annotations

import csv
import io
from pathlib import Path

import duckdb
import pytest
import yaml
from lxml import etree

from sdc_mapper import CARRIED, DECLARED, ERROR, EV_CARRIED, LOOKUP, LOST, NOT_REPRESENTABLE, VALID, Engine, load_mapping
from sdc_gdr2omop import OMOPMapper, mapping_path
from sdc_gdr2omop.writer import ddl_statements, load

ROOT = Path(__file__).resolve().parents[1]
VOCAB = ROOT / "tests" / "vocabulary-made-up"
SDC4 = "https://semanticdatacharter.com/ns/sdc4/"
PARTICIPANT = ("nhanes-participant", "xy8upneajsb8vdcmnve01g6g")
MEDICATION = ("nhanes-medication", "epbdfmvxc3gbh5f66hhb3o2m")


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    return Engine(schema_dir=tmp_path_factory.mktemp("schemas"))


def records(doc):
    return sorted((ROOT / "samples" / doc[0] / "records").glob("*.xml"))


def run(engine, doc, xml: bytes, mapper=None, mapping=None):
    return engine.map_record(xml, mapper or OMOPMapper(), mapping or load_mapping(mapping_path(doc[1])),
                             directory=str(ROOT / "samples" / doc[0]))


def rows(result, table):
    data = result.files.get(f"{table}.csv")
    return list(csv.DictReader(io.StringIO(data.decode()))) if data else []


def test_every_sample_record_loads_into_one_cdm(engine):
    """One mapper for the whole stream, so its ids do not collide; the DDL's keys and NOT NULLs hold for all."""
    con = duckdb.connect(":memory:")
    for s in ddl_statements():
        con.execute(s)
    mapper = OMOPMapper()
    for doc in (PARTICIPANT, MEDICATION):
        for f in records(doc):
            r = run(engine, doc, f.read_bytes(), mapper)
            assert r.outcome == VALID, (f.name, r.errors)
            load(r.files, con)
    count = lambda t: con.execute(f"select count(*) from {t}").fetchone()[0]   # noqa: E731
    assert count("person") == count("observation_period") == len(records(PARTICIPANT))
    assert count("drug_exposure") == len(records(MEDICATION))
    assert count("measurement") > 0 and count("observation") > 0 and count("condition_occurrence") > 0


def test_concepts_are_the_models_looked_up_in_the_users_vocabulary(engine):
    r = run(engine, PARTICIPANT, records(PARTICIPANT)[0].read_bytes(), OMOPMapper(VOCAB))
    systolic = [m for m in rows(r, "measurement") if m["measurement_concept_id"] == "2000000001"]
    assert systolic and all(m["unit_concept_id"] == "2000000003" and m["unit_source_value"] == "mmHg" for m in systolic)
    assert all(m["measurement_source_value"] == "r1ve12xphsb5hu2yjmhksw5h" for m in systolic), "the component's id"
    person = rows(r, "person")[0]
    assert person["gender_concept_id"] in ("2000000007", "2000000008")
    sys = next(v for v in r.report.values if v["label"] == "Systolic Blood Pressure")
    assert sys["class"] == LOOKUP


def test_an_icd10cm_code_maps_to_its_standard_concept(engine):
    for f in records(MEDICATION):
        r = run(engine, MEDICATION, f.read_bytes(), OMOPMapper(VOCAB))
        hit = [c for c in rows(r, "condition_occurrence") if c["condition_source_value"] == "E78.0"]
        if hit:
            assert hit[0]["condition_source_concept_id"] == "2000000013"
            assert hit[0]["condition_concept_id"] == "2000000014", "ICD-10-CM 'Maps to' the standard concept"
            return
    pytest.fail("no sample has E78.0")


def test_without_a_vocabulary_concepts_are_0_and_the_source_stays(engine):
    r = run(engine, PARTICIPANT, records(PARTICIPANT)[0].read_bytes())
    m = rows(r, "measurement")
    assert m and all(x["measurement_concept_id"] == "0" for x in m) and all(x["measurement_source_value"] for x in m)
    assert any(v["class"] == LOOKUP for v in r.report.values), "a lookup is the model's binding, vocabulary or not"


def test_a_drug_code_no_omop_vocabulary_carries_is_carried(engine):
    r = run(engine, MEDICATION, records(MEDICATION)[0].read_bytes(), OMOPMapper(VOCAB))
    drug = rows(r, "drug_exposure")[0]
    assert drug["drug_concept_id"] == "0" and drug["drug_source_value"].startswith("d")
    assert drug["drug_exposure_end_date"] == drug["drug_exposure_start_date"]
    v = next(v for v in r.report.values if v["label"] == "Generic Drug Code (RXDDRGID)")
    assert v["class"] == CARRIED


def test_a_race_omop_has_no_code_for_is_carried_as_source_text(engine):
    for f in records(PARTICIPANT):
        r = run(engine, PARTICIPANT, f.read_bytes())
        v = next((v for v in r.report.values if v["label"] == "Race/Ethnicity Self-Identification"), None)
        if v and v["class"] == CARRIED:
            assert rows(r, "person")[0]["race_source_value"] == "Hispanic, Latino, or Spanish"
            assert rows(r, "person")[0]["race_concept_id"] == "0"
            return
    pytest.fail("no sample answers 'Hispanic, Latino, or Spanish'")


# ---------------------------------------------------------------- Exceptional Values
def with_ev(xml: bytes, label: str, code="ASKR", name="Asked and Refused") -> bytes:
    from sdcreader import load_package, read_model
    model = read_model(load_package(ROOT / "samples" / PARTICIPANT[0], PARTICIPANT[1]))
    ids = {c.ct_id for c in model.components.values() if c.label == label}
    tree = etree.fromstring(xml)
    el = next(e for e in tree.iter() if isinstance(e.tag, str) and e.tag.startswith(f"{{{SDC4}}}ms-")
              and e.tag.split("ms-", 1)[1] in ids)
    after = el.find(f"{{{SDC4}}}act")
    after = el.find("label") if after is None else after
    ev = etree.Element(f"{{{SDC4}}}{code}")
    etree.SubElement(ev, "ev-name").text = name
    after.addnext(ev)
    return etree.tostring(tree)


def test_an_exceptional_value_is_carried_as_its_code(engine):
    r = run(engine, PARTICIPANT, with_ev(records(PARTICIPANT)[0].read_bytes(), "Systolic Blood Pressure"))
    assert r.outcome == VALID
    ev = r.report.exceptional[0]
    assert (ev["class"], ev["target_code"]) == (EV_CARRIED, "ASKR")
    m = [x for x in rows(r, "measurement") if x["value_source_value"] == "ASKR"]
    assert m and m[0]["value_as_number"] == "" and m[0]["measurement_source_value"] == "r1ve12xphsb5hu2yjmhksw5h"


def test_an_exceptional_birth_year_loses_the_person(engine):
    r = run(engine, PARTICIPANT, with_ev(records(PARTICIPANT)[0].read_bytes(), "Age"))
    assert r.outcome == VALID
    assert [e["class"] for e in r.report.exceptional] == [LOST]
    assert rows(r, "person") == []
    gone = [v for v in r.report.values if v.get("note", "").startswith("OMOP requires PERSON.year_of_birth")]
    assert {v["label"] for v in gone} >= {"Administrative Gender"}


def test_a_mapping_that_would_preserve_an_exceptional_value_is_refused(engine, tmp_path):
    doc = yaml.safe_load(mapping_path(PARTICIPANT[1]).read_text())
    doc["exceptional_values"] = {"ASKR": {"class": "preserved"}}
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    r = run(engine, PARTICIPANT, records(PARTICIPANT)[0].read_bytes(), mapping=load_mapping(p))
    assert r.outcome == ERROR and "cannot preserve" in r.errors[0]["reason"]


def test_a_component_with_no_rule_is_an_incomplete_mapping(engine, tmp_path):
    doc = yaml.safe_load(mapping_path(PARTICIPANT[1]).read_text())
    doc["rules"] = [r for r in doc["rules"] if r.get("sdc_type") != "XdQuantity"]
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    r = run(engine, PARTICIPANT, records(PARTICIPANT)[0].read_bytes(), mapping=load_mapping(p))
    assert r.outcome == ERROR and "no rule" in r.errors[0]["reason"]


def test_the_report_classes(engine):
    r = run(engine, PARTICIPANT, records(PARTICIPANT)[0].read_bytes())
    assert {v["class"] for v in r.report.values} <= {LOOKUP, DECLARED, CARRIED, NOT_REPRESENTABLE}
    survey = next(v for v in r.report.values if v["label"] == "Full Sample 2 Year Interview Weight (WTINT2YR)")
    assert survey["class"] == NOT_REPRESENTABLE and "survey's design" in survey["note"]
