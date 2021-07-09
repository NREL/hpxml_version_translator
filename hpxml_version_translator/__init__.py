import argparse
from hpxml_version_translator.converter import convert_hpxml2_to_3
import sys


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(description='HPXML Version Translator, convert an HPXML v2.x file to 3.0')
    parser.add_argument(
        'hpxml_input',
        help='Filename of hpxml v2.x file'
    )
    parser.add_argument(
        '-o', '--output',
        type=argparse.FileType('wb'),
        default=sys.stdout.buffer,
        help='Filename of output HPXML v3 file. If not provided, will go to stdout'
    )
    args = parser.parse_args(argv)
    convert_hpxml2_to_3(args.hpxml_input, args.output)


if __name__ == '__main__':
    main()  # pragma: no cover
