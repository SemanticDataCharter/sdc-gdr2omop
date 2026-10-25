"""Rules both NHANES models share with OMOP: the record's own clusters, the person every row is about, the date.

Paths are TABLE/column. `+TABLE` is a row of the value's own; `TABLE` is the record's one row of that table; `RECORD`
is what every row of the record takes (person_id, event_date). The concept of each row is the model's, looked up by
the mapper, so a rule names only where the value goes.
"""
#: NHANES publishes no exam or interview dates; every row of a 2017-2018 record takes the cycle's first day, and the
#: person's observation period is the cycle. Declared here, not found in the record.
CYCLE_START = "2017-01-01"
CYCLE_END = "2018-12-31"


def C(label, to, **kw):
    return {"cluster": label, "to": to, **kw}


def V(label, to, transform="copy", **kw):
    return {"component": label, "to": to, "transform": transform, **kw}


def T(sdc_type, to, note, transform="copy", **kw):
    return {"sdc_type": sdc_type, "to": to, "transform": transform, "note": note, **kw}


def OMIT_C(label, reason, **kw):
    return {"cluster": label, "to": "-", "transform": "omit", "reason": reason, **kw}


def OMIT(label, reason, **kw):
    return {"component": label, "to": "-", "transform": "omit", "reason": reason, **kw}


RECORD_CLUSTERS = [
    OMIT_C("Audit Event", "the record's audit event: OMOP CDM has no table for it"),
    OMIT_C("PROV Activity", "the record's provenance: OMOP CDM has no table for it"),
    OMIT_C("PROV Agent", "the record's provenance: OMOP CDM has no table for it"),
]


def person(also_period: bool):
    """The respondent's sequence number is the person, and the record's date is declared (CYCLE_START)."""
    also = [{"to": "RECORD/event_date", "transform": "constant", "value": CYCLE_START}]
    if also_period:
        also += [{"to": "OBSERVATION_PERIOD/observation_period_start_date", "transform": "constant", "value": CYCLE_START},
                 {"to": "OBSERVATION_PERIOD/observation_period_end_date", "transform": "constant", "value": CYCLE_END}]
    return V("Respondent Sequence Number (SEQN)", "RECORD/person_id", also=also)
