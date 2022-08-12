# pdf2gtfs
pdf2gtfs can be used to extract schedule data from timetables
and turn it into valid [gtfs](https://developers.google.com/transit/gtfs).

The following software is used
- [QLever](https://github.com/ad-freiburg/qlever), to search
[openstreetmap](https://www.openstreetmap.org) for the coordinates of the stops
- [ghostscript](https://www.ghostscript.com/), to strip the pdf of
anything that is not text, to improve the performance by order of magnitudes
- [pdfminer.six](https://pdfminersix.readthedocs.io/en/latest/), to extract
the chars from the pdf


# Getting started
## Prerequisites
- Linux or Windows
- python3.10 (required)
- All libraries in the [requirements.txt](requirements.txt)
- [ghostscript](https://www.ghostscript.com/) >= 9.56.1-1 (recommended)

Older versions may work as well, but only the versions given above
(and in the requirements.txt) are officially supported.

## Installation
1. Clone the repository: `git clone {repository_url}`
2. (Optional) Create a
[venv and activate it](https://docs.python.org/3/library/venv.html).
3. Install requirements:
```
cd pdf2gtfs
pip install -r requirements.txt
python src/main.py
```


# Configuration
pdf2gtfs will attempt to read any JSON file in the config directory
(`~/.config/pdf2gtfs/` or `%APPDATALOCAL%\pdf2gtfs\` depending on your system),
if it exists. Files which are read at a later point overwrite any values set
in previous configuration files.

For more information on how to configure pdf2gtfs, check out the
[default configuration](config.template.yaml).


# Usage
###### TODO: Check if this is working
`python -m src/main.py path/to/pdffile.pdf`


# Examples
###### TODO: Add

# License
Copyright 2022 Julius Heinzinger

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
