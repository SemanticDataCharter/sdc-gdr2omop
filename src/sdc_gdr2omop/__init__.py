"""sdc-gdr2omop: Governed Data Records as OMOP CDM 5.4 rows, through sdc-mapper.

    from sdc_mapper import Engine, load_mapping
    from sdc_gdr2omop import OMOPMapper, mapping_path
    result = Engine().map_record(xml, OMOPMapper("path/to/athena"), load_mapping(mapping_path("xy8upneajsb8vdcmnve01g6g")))

One mapping file per model, in `mappings/`. Registered with sdc-mapper as the target `omop`. The vocabulary is the
user's own Athena download, given as a directory or by the environment variable SDC_OMOP_VOCABULARY; none is shipped.
"""
from pathlib import Path

__version__ = "4.0.1"

MAPPINGS = Path(__file__).with_name("mappings")


def mapping_path(ct_id: str) -> Path:
    """The mapping file this package publishes for a model, by the model's identifier."""
    found = sorted(MAPPINGS.glob(f"*-{ct_id}.yaml"))
    if not found:
        raise FileNotFoundError(f"sdc-gdr2omop has no mapping for model {ct_id}")
    return found[-1]


from .mapper import OMOPMapper  # noqa: E402
from .vocabulary import Vocabulary  # noqa: E402

__all__ = ["OMOPMapper", "Vocabulary", "mapping_path", "MAPPINGS", "__version__"]
