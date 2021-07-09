from lxml import objectify
import pathlib
import tempfile

from hpxml_version_translator.converter import convert_hpxml_to_3


hpxml_dir = pathlib.Path(__file__).resolve().parent / 'hpxml_files'


def convert_hpxml_and_parse(input_filename):
    with tempfile.NamedTemporaryFile('w+b') as f_out:
        convert_hpxml_to_3(input_filename, f_out)
        f_out.seek(0)
        root = objectify.parse(f_out).getroot()
    return root


def test_version_change():
    root = convert_hpxml_and_parse(hpxml_dir / 'hpxml1_version_change.xml')
    assert root.attrib['schemaVersion'] == '3.0'
