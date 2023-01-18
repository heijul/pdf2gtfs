# pdf2gtfs

pdf2gtfs can be used to extract schedule data from PDF timetables
and turn it into valid [GTFS](https://developers.google.com/transit/gtfs).

It was created as a bachelor's project at the chair of 'Algorithms and
Datastructures'
of the Freiburg University.

A blogpost, detailing its usage can be
found [here](https://ad-blog.informatik.uni-freiburg.de/post/transform-pdf-timetables-into-gtfs).

## Getting started

### Prerequisites

- Linux or Windows
- python3.10 or higher (required)
- All libraries in the [requirements.txt](requirements.txt)
- [ghostscript](https://www.ghostscript.com/) >= 9.56.1-1 (recommended)

Older versions may work as well, but only the versions given above
(and in the requirements.txt) are officially supported.

### Installation

1. Clone the repository: `git clone {repository_url}`
2. (Optional) Create a
   [venv and activate it](https://docs.python.org/3/library/venv.html).
3. Install the requirements:

```shell
> cd pdf2gtfs
> pip install -r requirements.txt
> python src/main.py path/to/a/pdf/file.pdf
```

## Configuration

pdf2gtfs will attempt to read any JSON file in the config directory
(`~/.config/pdf2gtfs/` or `%APPDATALOCAL%\pdf2gtfs\` depending on your system),
if it exists. Files which are read at a later point overwrite any values set
in previous configuration files.

For more information on how to configure pdf2gtfs, check out the
[default configuration](config.template.yaml).

## Usage

`python src/main.py [options]... path/to/pdffile.pdf`

## Examples

The following examples can be run from the pdf2gtfs directory.

### Example 1: Line 1 of the VAG in Freiburg

`python src/main.py --config=examples/vag_1.conf examples/vag_1.pdf`

### Example 2: Line S1 of the KVV in Karlsruhe

`python src/main.py --config=examples/kvv_s1.conf examples/kvv_s1.pdf`

## Detailed description

A complete description can be found in the
[blogpost](https://ad-blog.informatik.uni-freiburg.de/post/transform-pdf-timetables-into-gtfs/).
The way pdf2gtfs works is as follows:

### Transform the given pdf into a datastructure

1. Use [ghostscript](https://www.ghostscript.com/)
   to remove all images and vector drawings from the pdf
2. Use [pdfminer.six](https://pdfminersix.readthedocs.io/en/latest/)
   to extract all characters from the pdf
3. Group chars into lines, depending on their y-coordinate
4. Group lines into tables, depending on their distance to each other

### Turn the tables into gtfs (stop coordinates are added later)

1. If an `agency.txt` is given using the `input_files` option and it
   contains a single entry, use that agency by default. If it contains
   multiple entries, ask the user to choose, which agency should be used.
2. If a `stops.txt` is given using the `input_files` option, search it for the
   stops.
3. Create basic skeleton of required gtfs files
4. In case the tables contain annotations, create a new calendar.txt entry
   for each annotation and date combination.
    * Ask the user to input dates, where there is an exception in the service,
      which are added to the calendar_dates.txt
5. Iterate through the TimeTableEntries of all TimeTables and create a new entry
   data to the
   `stop_times.txt`.

### Search for the coordinates of the stops.

This is only done, if there is no `stops.txt` input file, or if the given file
does not contain all necessary stops.

1. Get a list of all stop locations along with their name, type and some
   attributes from [openstreetmap (osm)](https://www.openstreetmap.org)
   using [QLever](https://github.com/ad-freiburg/qlever).
2. Normalize the names of the stops by stripping any non-letter symbols
   and expanding any abbreviations
3. Add basic costs:
    * Name costs, based on the lowest edit distance between a stops name
      and any of the node's names.
    * Node costs, based on the selected gtfs_routetype and the attributes of
      the node.
4. Use Dijkstra's algorithm, to find the nodes with the lowest cost. The cost
   of a node, is simply the sum of its name-, node- and travel cost. The travel
   cost is calculated, using a "closer-is-better" approach.
5. If any of the stops was found in the `stops.txt` file (if given), it's
   location will be used instead of checking the OSM data.

## License

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
