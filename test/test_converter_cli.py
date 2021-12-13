import io
from lxml import objectify
import pathlib
import tempfile

from hpxml_version_translator import main
from hpxml_version_translator.converter import get_hpxml_versions


hpxml_dir = pathlib.Path(__file__).resolve().parent / "hpxml_v2_files"


def test_cli(capsysbinary):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = pathlib.Path(tmpdir).resolve()
        input_filename = str(hpxml_dir / "version_change.xml")
        output_filename = str(tmppath / "out.xml")
        main([input_filename, "-o", output_filename])
        root = objectify.parse(output_filename).getroot()
        assert root.attrib["schemaVersion"] == "3.0"

    main([input_filename])
    f = io.BytesIO(capsysbinary.readouterr().out)
    root = objectify.parse(f).getroot()
    assert root.attrib["schemaVersion"] == "3.0"


def test_cli_to_v2(capsysbinary):
    input_filename = str(
        pathlib.Path(__file__).resolve().parent
        / "hpxml_v1_files"
        / "version_change.xml"
    )
    main([input_filename, "-v", "2.3"])
    f = io.BytesIO(capsysbinary.readouterr().out)
    root = objectify.parse(f).getroot()
    assert root.attrib["schemaVersion"] == "2.3"


def test_schema_versions():
    hpxml_versions = get_hpxml_versions()
    assert "3.0" in hpxml_versions
    assert "2.3" in hpxml_versions
    assert "1.1.1" not in hpxml_versions

    hpxml_versions = get_hpxml_versions(major_version=3)
    assert "3.0" in hpxml_versions
    assert "2.3" not in hpxml_versions
    assert "1.1.1" not in hpxml_versions
