# pdf2gtfs
pdf2gtfs can be used to extract schedule data from timetables
and turn it into valid [gtfs](https://developers.google.com/transit/gtfs).

It was created as a bachelor's project at the chair of 'Algorithms and Datastructures'
of the Freiburg University.


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


## Detailed description
The way pdf2gtfs works is as follows:
### Transform the given pdf into a datastructure
1. use [ghostscript](https://www.ghostscript.com/)
   to remove all images and vector drawings from the pdf
2. use [pdfminer.six](https://pdfminersix.readthedocs.io/en/latest/)
   to extract all characters from the pdf
3. group chars into lines, depending on their y-coordinate
4. group lines into tables, depending on their distance to each other

### Turn the tables into gtfs (stop coordinates are added later)
1. If an agency.txt already exists and it
    1. contains a single entry, use that agency by default
    2. contains multiple entries, ask the user to input the agency that should be used
2. If a stops.txt exists, use the given stops, otherwise and in case a stop was not found,
   create an entry for each missing stop
3. Create basic skeleton of required gtfs files
4. In case the tables contain annotations, create a new calendar.txt entry
   for each annotation and date combination.
    1. Ask the user to input dates, where there is an exception in the service,
       which are added to the calendar_dates.txt
5. Iterate through the tables by column and
    1. if the column contains timetable data: add a new entry to stop_times.txt
    2. if the column contains a repeat identifier: add multiple entries to
       stop_times.txt with the given frequency until the time of the current entry
       is greater than the time of the next column
6. Add entries in calendar_dates.txt based on

### Search for the coordinates of the stops (in case stops.txt does not exist).
1. get a list of all stop locations along with their name and type
   from [openstreetmap (osm)](https://www.openstreetmap.org) using [QLever](https://github.com/ad-freiburg/qlever)
2. normalize the names of the stops by stripping any non-letter symbols
   and expanding any abbreviations
3. try to find the combination of stops such that
    1. all stops are mapped to a location (if possible),
       preferring locations with names, which have a lower edit distance to the stop name
    2. the overall distance is minimized,
       preferring locations closer to the next stop


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
