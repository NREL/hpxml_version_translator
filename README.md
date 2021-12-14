# HPXML Version Translator

This package converts an HPXML file to a newer version.

## Requirements

Python >=3.6

## Installation

In general, we recommended to use a virtual environment or conda environment and then installing with pip, like so:

```
pip install hpxml_version_translator
```

### Developer Installation

If you want to do work on the repo, clone this repo and install in development mode.

```
cd path/to/repo
pip install -e ".[dev]"
```

## How to use

### Command Line

```
hpxml_version_translator -h
usage: hpxml_version_translator [-h] [-o OUTPUT] [-v {2.0,2.1,2.2,2.2.1,2.3,4.0,3.0}] hpxml_input

HPXML Version Translator, convert an HPXML file to a newer version

positional arguments:
  hpxml_input           Filename of hpxml file

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Filename of output HPXML file. If not provided, will go to stdout
  -v {2.0,2.1,2.2,2.2.1,2.3,4.0,3.0}, --to_hpxml_version {2.0,2.1,2.2,2.2.1,2.3,4.0,3.0}
                        Version of HPXML to translate to, default: 3.0
```

### In a Python script

```python
from hpxml_version_translator import convert_hpxml_to_version

convert_hpxml_to_version("3.0", "path/to/in.xml", "path/to/out.xml")
```

It also works with path-like objects and binary file-like objects.