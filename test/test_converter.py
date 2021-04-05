from lxml import objectify
import pathlib
import tempfile

from hpxml2to3.converter import convert_hpxml2_to_3


hpxml_dir = pathlib.Path(__file__).resolve().parent / 'hpxml_files'

def test_version_change():
    with tempfile.TemporaryFile('w+b') as f_out:
        convert_hpxml2_to_3(hpxml_dir / 'version_change.xml', f_out)
        f_out.seek(0)
        root = objectify.parse(f_out).getroot()
        assert root.attrib['schemaVersion'] == '3.0'
