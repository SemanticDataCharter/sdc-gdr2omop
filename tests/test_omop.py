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
#: NHANES Participant 4.2.0; 4.2.3, which composes the NIH CDE library's corrected "Are you pregnant now?"
#: (E-2026-10-01); and 4.2.4, whose value bindings name codes their terminologies confirm (E-2026-10-03). Every mapping
#: stays published: records made on the retired models still exist.
PARTICIPANTS = [("nhanes-participant", "xy8upneajsb8vdcmnve01g6g"), ("nhanes-participant-423", "eehpfapwgvxtzdrofgstdcfs"),
                ("nhanes-participant-424", "tp5pg0u4dasqarie0b3ujn2u"), ("nhanes-participant-430", "drjvqb171q9pqwcdq6nxxrr4"),
                ("nhanes-participant-431", "fafj69kdii37997sy7dpsz13")]
MEDICATION = ("nhanes-medication", "epbdfmvxc3gbh5f66hhb3o2m")
MEDICATION_430 = ("nhanes-medication-430", "plc9gto1kzy244g1r2op257f")


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    return Engine(schema_dir=tmp_path_factory.mktemp("schemas"))


@pytest.fixture(params=PARTICIPANTS, ids=["4.2.0", "4.2.3", "4.2.4", "4.3.0", "4.3.1"])
def participant(request):
    return request.param


def records(doc):
    return sorted((ROOT / "samples" / doc[0] / "records").glob("*.xml"))


def examined(doc) -> bytes:
    """The first sample record with a blood pressure reading: the cases below need the exam's measurements."""
    return next(x for x in (f.read_bytes() for f in records(doc)) if b"r1ve12xphsb5hu2yjmhksw5h" in x)


def run(engine, doc, xml: bytes, mapper=None, mapping=None):
    return engine.map_record(xml, mapper or OMOPMapper(), mapping or load_mapping(mapping_path(doc[1])),
                             directory=str(ROOT / "samples" / doc[0]))


def rows(result, table):
    data = result.files.get(f"{table}.csv")
    return list(csv.DictReader(io.StringIO(data.decode()))) if data else []


def test_every_sample_record_loads_into_one_cdm(engine, participant):
    """One mapper for the whole stream, so its ids do not collide; the DDL's keys and NOT NULLs hold for all. One CDM
    per participant model: the two samples share participants, and a person is one row."""
    con = duckdb.connect(":memory:")
    for s in ddl_statements():
        con.execute(s)
    mapper = OMOPMapper()
    for doc in (participant, MEDICATION):
        for f in records(doc):
            r = run(engine, doc, f.read_bytes(), mapper)
            assert r.outcome == VALID, (f.name, r.errors)
            load(r.files, con)
    count = lambda t: con.execute(f"select count(*) from {t}").fetchone()[0]   # noqa: E731
    assert count("person") == count("observation_period") == len(records(participant))
    assert count("drug_exposure") == len(records(MEDICATION))
    assert count("measurement") > 0 and count("observation") > 0 and count("condition_occurrence") > 0


def test_concepts_are_the_models_looked_up_in_the_users_vocabulary(engine, participant):
    r = run(engine, participant, examined(participant), OMOPMapper(VOCAB))
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


def test_without_a_vocabulary_concepts_are_0_and_the_source_stays(engine, participant):
    r = run(engine, participant, examined(participant))
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


def test_a_race_omop_has_no_code_for_is_carried_as_source_text(engine, participant):
    for f in records(participant):
        r = run(engine, participant, f.read_bytes())
        v = next((v for v in r.report.values if v["label"] == "Race/Ethnicity Self-Identification"), None)
        if v and v["class"] == CARRIED:
            assert rows(r, "person")[0]["race_source_value"] == "Hispanic, Latino, or Spanish"
            assert rows(r, "person")[0]["race_concept_id"] == "0"
            return
    pytest.fail("no sample answers 'Hispanic, Latino, or Spanish'")


# ---------------------------------------------------------------- Exceptional Values
def with_ev(doc, xml: bytes, label: str, code="ASKR", name="Asked and Refused") -> bytes:
    from sdcreader import load_package, read_model
    model = read_model(load_package(ROOT / "samples" / doc[0], doc[1]))
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


def test_an_exceptional_value_is_carried_as_its_code(engine, participant):
    r = run(engine, participant, with_ev(participant, examined(participant), "Systolic Blood Pressure"))
    assert r.outcome == VALID
    ev = r.report.exceptional[0]
    assert (ev["class"], ev["target_code"]) == (EV_CARRIED, "ASKR")
    m = [x for x in rows(r, "measurement") if x["value_source_value"] == "ASKR"]
    assert m and m[0]["value_as_number"] == "" and m[0]["measurement_source_value"] == "r1ve12xphsb5hu2yjmhksw5h"


def test_an_exceptional_birth_year_loses_the_person(engine, participant):
    r = run(engine, participant, with_ev(participant, examined(participant), "Age"))
    assert r.outcome == VALID
    assert [e["class"] for e in r.report.exceptional] == [LOST]
    assert rows(r, "person") == []
    gone = [v for v in r.report.values if v.get("note", "").startswith("OMOP requires PERSON.year_of_birth")]
    assert {v["label"] for v in gone} >= {"Administrative Gender"}



def test_a_lost_persons_carried_values_are_not_exceptional(engine, participant):
    """CARRIED and EV_CARRIED are the same word; a person lost to an exceptional birth year takes its race, carried as
    source text, with it as not representable, not as a lost Exceptional Value (4.0.3: such a record was refused)."""
    for f in records(participant):
        x = f.read_bytes()
        if b"r1ve12xphsb5hu2yjmhksw5h" not in x or b"Hispanic, Latino, or Spanish" not in x:
            continue
        r = run(engine, participant, with_ev(participant, x, "Age"))
        assert r.outcome == VALID, r.errors
        race = [v for v in r.report.values if v["label"] == "Race/Ethnicity Self-Identification"]
        assert race and all(v["class"] == NOT_REPRESENTABLE for v in race)
        assert [e["class"] for e in r.report.exceptional] == [LOST]
        return
    pytest.fail("no examined sample answers 'Hispanic, Latino, or Spanish'")

def test_a_mapping_that_would_preserve_an_exceptional_value_is_refused(engine, participant, tmp_path):
    doc = yaml.safe_load(mapping_path(participant[1]).read_text())
    doc["exceptional_values"] = {"ASKR": {"class": "preserved"}}
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    r = run(engine, participant, examined(participant), mapping=load_mapping(p))
    assert r.outcome == ERROR and "cannot preserve" in r.errors[0]["reason"]


def test_a_component_with_no_rule_is_an_incomplete_mapping(engine, participant, tmp_path):
    doc = yaml.safe_load(mapping_path(participant[1]).read_text())
    doc["rules"] = [r for r in doc["rules"] if r.get("sdc_type") != "XdQuantity"]
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    r = run(engine, participant, examined(participant), mapping=load_mapping(p))
    assert r.outcome == ERROR and "no rule" in r.errors[0]["reason"]


def test_the_report_classes(engine, participant):
    r = run(engine, participant, examined(participant))
    assert {v["class"] for v in r.report.values} <= {LOOKUP, DECLARED, CARRIED, NOT_REPRESENTABLE}
    survey = next(v for v in r.report.values if v["label"] == "Full Sample 2 Year Interview Weight (WTINT2YR)")
    assert survey["class"] == NOT_REPRESENTABLE and "survey's design" in survey["note"]


def test_the_pregnancy_answers_carry_the_codes_their_model_binds(engine):
    """E-2026-10-01: NIH's record bound each answer of "Are you pregnant now?" to the next value's LOINC code. A record
    made on 4.2.0 carries that binding, and the mapping looks up what the model says; 4.2.3 binds the right codes."""
    concepts = {"2000000015": "LA15173-0", "2000000016": "LA26683-5", "2000000017": "LA4489-6"}
    expected = {PARTICIPANTS[0]: ("owjt9bcgisxfbco8qnddo2fq", {"Yes": "LA26683-5", "No": "LA4489-6", "Unknown": "LA15173-0"}),
                PARTICIPANTS[1]: ("zmpqfc6tb0o2hgu8qs6lj8tp", {"Yes": "LA15173-0", "No": "LA26683-5", "Unknown": "LA4489-6"}),
                PARTICIPANTS[2]: ("zmpqfc6tb0o2hgu8qs6lj8tp", {"Yes": "LA15173-0", "No": "LA26683-5", "Unknown": "LA4489-6"})}
    for doc, (component, codes) in expected.items():
        seen = {}
        for f in records(doc):
            r = run(engine, doc, f.read_bytes(), OMOPMapper(VOCAB))
            for o in rows(r, "observation"):
                if o["observation_source_value"] == component:
                    seen[o["value_source_value"]] = concepts.get(o["value_as_concept_id"])
        assert seen and all(codes[answer] == code for answer, code in seen.items()), (doc, seen)


def _answers(engine, doc) -> dict[tuple[str, str], str]:
    """(SEQN, answer text) -> the code of its value_as_concept_id in the made-up vocabulary ("0": no concept)."""
    import re
    codes = {r["concept_id"]: r["concept_code"] for r in csv.DictReader(open(VOCAB / "CONCEPT.csv"), delimiter="\t")}
    out = {}
    for f in records(doc):
        xml = f.read_bytes()
        seqn = re.search(rb"DEMO_J\.XPT#SEQN=(\d+)", xml).group(1).decode()
        for o in rows(run(engine, doc, xml, OMOPMapper(VOCAB)), "observation"):
            if o["value_source_value"]:
                out[(seqn, o["value_source_value"])] = codes.get(o["value_as_concept_id"], "0")
    return out


def test_the_corrected_value_bindings_reach_value_as_concept_id(engine):
    """E-2026-10-03: 4.2.3 bound every level of the difficulty scale to NCIt Unknown, both pregnancy-at-exam answers to
    C25191 (Person Name), both citizenship answers to C41130 (Significant). For the same participants, 4.2.4 looks up
    the codes its terminologies confirm."""
    before, after = _answers(engine, PARTICIPANTS[1]), _answers(engine, PARTICIPANTS[2])
    expected = {"No difficulty": ("C17998", "C121736"), "Some difficulty": ("C17998", "C121739"),
                "Much difficulty": ("C17998", "C121740"), "Unable to do": ("C17998", "C121742"),
                "Not pregnant at exam": ("C25191", "C82475"), "Citizen by birth or naturalization": ("C41130", "C90516"),
                "College graduate or above": ("C39303", "C159746")}
    for answer, (old, new) in expected.items():
        shared = [k for k in before if k[1] == answer and k in after]
        assert shared, answer
        assert all(before[k] == old and after[k] == new for k in shared), (answer, [(before[k], after[k]) for k in shared])


def test_a_value_defined_by_a_codebook_page_has_no_concept(engine):
    """E-2026-10-03 defines a value no concept says exactly by the agency's codebook (DEMO_J.htm#DMDCITZN,
    PFQ_J.htm). A codebook page is not a code: the value has no concept, its text is the source value, and no cell
    names the codebook or the variable its anchor points at."""
    doc = PARTICIPANTS[2]
    after = _answers(engine, doc)
    for answer in ("Not a citizen of the US", "Less than 9th grade", "Do not do this activity"):
        found = [code for (_, text), code in after.items() if text == answer]
        assert found and set(found) == {"0"}, (answer, found)
    for f in records(doc):
        for data in run(engine, doc, f.read_bytes(), OMOPMapper(VOCAB)).files.values():
            text = data.decode()
            assert not any(x in text for x in ("DEMO_J.htm", "PFQ_J.htm", "DMDCITZN", "DMDEDUC2")), f.name



def _with(doc, pattern: bytes):
    return [x for x in (f.read_bytes() for f in records(doc)) if pattern in x]


def test_every_medication_430_record_maps_and_loads(engine):
    """4.3.0: a medicine whose name is unknown, refused or not known is a record, with an Exceptional Value; it still
    maps (the name has no OMOP column, so its Exceptional Value is lost, not an error)."""
    con = duckdb.connect(":memory:")
    for s in ddl_statements():
        con.execute(s)
    mapper = OMOPMapper()
    for f in records(MEDICATION_430):
        r = run(engine, MEDICATION_430, f.read_bytes(), mapper)
        assert r.outcome == VALID, (f.name, r.errors)
        load(r.files, con)
    assert con.execute("select count(*) from drug_exposure").fetchone()[0] > 0


def test_an_nhanes_prevention_code_is_never_icd10cm(engine):
    """FAIR 4.3.0: I21.P (prevent heart attack) is NHANES's code, not ICD-10-CM. It is an OBSERVATION with no concept,
    the code and NHANES's description as its source value and text, and never a condition. Even a vocabulary with an
    ICD10CM concept coded I21.P does not give it one: the code is never looked up as ICD-10-CM."""
    xs = _with(MEDICATION_430, b"Prevention Reason Code (NHANES)")
    assert xs, "the sample has prevention codes"
    for xml in xs:
        r = run(engine, MEDICATION_430, xml, OMOPMapper(VOCAB))
        assert r.outcome == VALID, r.errors
        codes = [c.decode() for c in __import__("re").findall(rb"Prevention Reason Code \(NHANES\)</label>\s*<xdstring-value>([^<]+)", xml)]
        obs = {o["observation_source_value"]: o for o in rows(r, "observation")}
        for code in codes:
            o = obs[code]
            assert o["observation_concept_id"] == "0" and o["value_as_string"].lower().startswith("prevent")
            assert not o.get("observation_source_concept_id") or o["observation_source_concept_id"] == "0"
        assert not {c["condition_source_value"] for c in rows(r, "condition_occurrence")} & set(codes)


def test_an_exceptional_value_on_an_omitted_component_is_lost_not_an_error(engine):
    """The drug's name has no OMOP column; an unknown name (UNK) is an Exceptional Value with nowhere to go: lost."""
    xml = next(x for x in records(MEDICATION_430) for x in [x.read_bytes()]
               if __import__("re").search(rb"Generic Drug Name \(RXDDRUG\)</label>\s*<sdc4:UNK>", x))
    r = run(engine, MEDICATION_430, xml)
    assert r.outcome == VALID, r.errors
    assert [(e["class"]) for e in r.report.exceptional] == [LOST]


def test_a_refused_answer_is_carried_as_its_code_never_as_a_value(engine):
    """FAIR 4.3.0: a refused answer is ASKR in place of the answer: its row's value source is ASKR, and it has no value."""
    doc = ("nhanes-participant-430", "drjvqb171q9pqwcdq6nxxrr4")
    xml = next(x for x in (f.read_bytes() for f in records(doc)) if b"<sdc4:ASKR>" in x)
    r = run(engine, doc, xml, OMOPMapper(VOCAB))
    assert r.outcome == VALID, r.errors
    askr = [o for o in rows(r, "observation") if o.get("value_source_value") == "ASKR"]
    assert askr and all(o["value_as_concept_id"] in ("", "0") and not o.get("value_as_number") for o in askr)
    assert EV_CARRIED in {e["class"] for e in r.report.exceptional}


def test_an_unknown_reason_is_not_a_condition(engine):
    """FAIR 4.3.0: SEQN 96375's medication reason is ASKU in place of its ICD-10-CM code. An unknown reason is not a
    condition: no CONDITION_OCCURRENCE row (one with concept 0 and source ASKU would be counted as a recorded
    condition); the Exceptional Value is lost, and the report says why."""
    import re
    xml = next(x for x in (f.read_bytes() for f in records(MEDICATION_430))
               if b"SEQN=96375;" in x and re.search(rb"Diagnosis Code \(ICD-10-CM\)</label>\s*<sdc4:ASKU>", x))
    r = run(engine, MEDICATION_430, xml)
    assert r.outcome == VALID, r.errors
    assert rows(r, "condition_occurrence") == []
    lost = [e for e in r.report.exceptional if e["class"] == LOST]
    assert [e["code"] for e in lost] == ["ASKU"]
    why = next(v for v in r.report.values if v["position"] == lost[0]["position"])
    assert "no condition to record" in why.get("note", "")
    assert not any("ASKU" in o.values() for t in ("observation", "measurement", "drug_exposure") for o in rows(r, t))



def test_a_part_of_a_compound_concept_is_not_the_elements_concept(engine):
    """4.3.1's NIH CDE answers carry their compound concept as several dcterms:subject parts (NIH CDE R-2026-10-27);
    "Are you pregnant now?" is Person + Current + Pregnancy + ... . No part is the observation's concept: with a
    vocabulary that has NCIt Person, the 4.3.1 row's concept stays 0. The 4.3.0 model claimed Person as an exact match,
    and the row follows that claim; 4.3.1 is the revision that withdraws it."""
    def pregnancy_rows(doc, ct):
        for f in records(doc):
            r = run(engine, doc, f.read_bytes(), OMOPMapper(VOCAB))
            got = [x for x in rows(r, "observation") if x["observation_source_value"] == ct]
            if got:
                return got
        raise AssertionError("no participant in the sample answers the question")
    new = pregnancy_rows(("nhanes-participant-431", "fafj69kdii37997sy7dpsz13"), "z3dy86uraka0bmuuvfdzf0ev")
    assert all(x["observation_concept_id"] == "0" and x["observation_source_concept_id"] in ("", "0") for x in new)
    old = pregnancy_rows(("nhanes-participant-430", "drjvqb171q9pqwcdq6nxxrr4"), "ukvlpa3hvurit0wuzkkgh7nx")
    assert all(x["observation_source_concept_id"] == "2000000033" for x in old)   # the 4.3.0 model's exact-match claim
