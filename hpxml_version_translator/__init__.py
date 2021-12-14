import argparse
from hpxml_version_translator.converter import (
    convert_hpxml_to_version,
    get_hpxml_versions,
)
import sys


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description="HPXML Version Translator, convert an HPXML file to a newer version"
    )
    parser.add_argument("hpxml_input", help="Filename of hpxml file")
    parser.add_argument(
        "-o",
        "--output",
        type=argparse.FileType("wb"),
        default=sys.stdout.buffer,
        help="Filename of output HPXML file. If not provided, will go to stdout",
    )
    parser.add_argument(
        "-v",
        "--to_hpxml_version",
        type=str,
        default="3.0",
        choices=get_hpxml_versions(),
        help="Version of HPXML to translate to, default: 3.0",
    )
    args = parser.parse_args(argv)
    convert_hpxml_to_version(args.to_hpxml_version, args.hpxml_input, args.output)


if __name__ == "__main__":
    main()  # pragma: no cover
