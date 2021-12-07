import io
from lxml import objectify
import pathlib
import tempfile

from hpxml_version_translator import main


hpxml_dir = pathlib.Path(__file__).resolve().parent / "hpxml_files"


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
