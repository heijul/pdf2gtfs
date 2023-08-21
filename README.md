# pdf2gtfs

pdf2gtfs can be used to extract schedule data from PDF timetables
and turn it into valid [GTFS](https://developers.google.com/transit/gtfs).

It was created as a Bachelor's project + thesis at the chair of 'Algorithms and
Datastructures' of the Freiburg University.

The Bachelor's thesis, which goes into more detail and adds an evaluation, can be found 
[here](https://ad-publications.informatik.uni-freiburg.de/theses/Bachelor_Julius_Heinzinger_2023.pdf).
A (shorter) blogpost detailing its usage can be found
[here](https://ad-blog.informatik.uni-freiburg.de/post/transform-pdf-timetables-into-gtfs),
though some parts are outdated.


## Getting started

### Prerequisites

- Linux or Windows
- python3.10 or higher (required)
- [ghostscript](https://www.ghostscript.com/) >= 9.56.1-1 (recommended)

Older versions may work as well, but only the versions given above are officially supported.

### Installation and Usage

Note that using pip won't install the dependencies required only for development.

#### 1. Clone the repository: 
   ```shell
   git clone https://github.com/heijul/pdf2gtfs.git
   cd pdf2gtfs
   ```
#### 2. (Optional) Create a venv and activate it [(more info)](https://docs.python.org/3/library/venv.html):
   ```shell
   python3.11 -m venv venv
   source venv/bin/activate
   ``` 
   Under Windows, you have to activate the venv using ´./venv/bin/activate´.

#### 3. Install pdf2gtfs using pip or poetry.
   Note: With pip you will have to manually install the development requirements 
   (Defined in [pyproject.toml](pyproject.toml)).

   Using pip:
   ```shell
   pip install .
   ```
   Using poetry (requires poetry, of course):
   ```shell
   poetry install 
   ```
   Using poetry, but also install the development requirements:
   ```shell
   poetry install --with=dev
   ```

#### 4. (Optional) Run the tests.
   Using unittest:
   ```shell
   python -m unittest discover test 
   ```
   Using pytest:
   ```shell
   pytest test
   ```

#### 5. Run pdf2gtfs.
   ```shell
   pdf2gtfs -h
   ```
   This will provide help on the usage of pdf2gtfs.


## Configuration

pdf2gtfs will read the provided config file in order.
The [default configuration](src/pdf2gtfs/config.template.yaml) will be read first,
and any provided config files will be read in the order they were given.
Later configurations override previous configurations.

For more information on the config keys and their possible values, check out the
[default configuration](src/pdf2gtfs/config.template.yaml).


## Examples

TODO: Some issues, not sure everything works with the new algorithm 
(See [Issue #58](https://github.com/heijul/pdf2gtfs/issues/58))

The following examples can be run from the `examples` directory and show
how some config values change the accuracy of the detected locations, as well
as whether the pdf can be read at all. The `base.yaml` config only contains
some basic output settings, used by all examples.

**Before you run these, switch to the `examples` directory: `cd examples`**

#### Example 1: Tram Line 1 of the [VAG](https://www.vag-freiburg.de/)

Uses the default configuration, with the exception of the routetype.

`pdf2gtfs --config=base.yaml --config=vag_1.yaml vag_1.pdf`

#### Example 2: Subway Line S1 of the [KVV](https://www.kvv.de/)

The `max_row_distance` needs to be adjusted, to read this PDF properly.

`pdf2gtfs --config=base.yaml --config=kvv_s1.yaml kvv_s1.pdf`

#### Example 3: RegionalExpress Lines RE2/RE3 of the [GVH](https://www.gvh.de/)

The `close_node_check`, needs to be disabled, because it incorrectly disregards
valid locations, that seem too far away.

`pdf2gtfs --config=base.yaml --config=gvh_re2_re3.yaml gvh_re2_re3.pdf`

#### Example 4: Bus Line 680 of the [Havelbus](https://www.havelbus.de/)

Here, disabling the `close_node_check` leads to far better results as well.
Note that the config also contains some other settings, which lead to a
similar result.

`pdf2gtfs --config=base.yaml --config=havelbus_680.yaml havelbus_680.pdf`

#### Example 5: Line G10 of the [RMV](https://www.rmv.de/)

Reading of page 4 currently fails and reading more than one page leads to
worse results in the location detection. This may sometimes happen, because
the average of all locations for a specific stop is used.

`pdf2gtfs --config=base.yaml --config=rmv_g10.yaml rmv_g10.pdf`


## How does it work

In principle, pdf2gtfs works in 3 steps:
1. Extract the timetable data from the PDF
2. Create the GTFS in memory
3. Detect the locations of the stops using the stop names and their order.

Finally, the GTFS feed is saved on disk, after adding the locations.

In the following are some rough descriptions 
on how each of the previously mentioned steps is performed. 

### Extract the timetable data from the PDF

1. Use [ghostscript](https://www.ghostscript.com/)
   to remove all images and vector drawings from the PDF
2. Use [pdfminer.six](https://pdfminersix.readthedocs.io/en/latest/)
   to extract the text from the PDF
3. Split the LTTextLine objects of pdfminer.six into words
4. Detect the words that are times using the `time_format` config-key
5. Define the body of the table using the times 
6. Add cells to the table that overlap with its rows/columns

### Create the GTFS in memory

1. If an `agency.txt` is given using the `input_files` option, and it
   contains a single entry, use that agency by default. If it contains
   multiple entries, ask the user to choose, which agency should be used.
2. If a `stops.txt` is given using the `input_files` option, search it for the
   stops.
3. Create basic skeleton of required GTFS files
4. In case the tables contain annotations, create a new `calendar.txt` entry
   for each annotation and date combination.
    * Ask the user to input dates, where there is an exception in the service,
      which are added to the calendar_dates.txt
5. Iterate through the TimeTableEntries of all TimeTables and create a new entry
   data to the `stop_times.txt`.

### Detect the locations of the stops using the stop names and their order 

This is only done, if there is no `stops.txt` input file, or if the given file
does not contain all necessary stops.

1. Get a list of all stop locations (nodes) along with their name, type and some
attributes from [OpenStreetMap (OSM)](https://www.openstreetmap.org)
using [QLever](https://github.com/ad-freiburg/qlever).
2. Normalize the names of the nodes by stripping any non-letter symbols
and expanding any abbreviations
3. For each stop of the detected tables, find those nodes that contain 
every word of the (normalized) stop name.
4. Add basic costs:
   * Name costs, based on the difference in length between a stops name 
   and any of the node's names. (This works, because of the normalization)
   * Node costs, based on the selected gtfs_routetype and the attributes of
   the node.
5. Use Dijkstra's algorithm, to find the nodes with the lowest cost. The cost
   of a node, is simply the sum of its name-, node- and travel cost. The travel
   cost is calculated using either a "closer-is-better" approach 
   or a "closer-to-expected-distance-is-better" approach.
6. If any of the stops was found in the `stops.txt` file (if given), it's
   location will be used instead of checking the OSM data.
7. If the location of a stop was not found, it is interpolated 
   using the surrounding stop locations.

The first two steps are generally the slowest steps of the location detection.
Therefore, we cache the result and use the cache, if possible.


## More information

The new table extraction, as well as the overall process and evaluation of pdf2gtfs are detailed in my
[Bachelor's thesis](https://ad-publications.informatik.uni-freiburg.de/theses/Bachelor_Julius_Heinzinger_2023.pdf).
There is also a [blogpost](https://ad-blog.informatik.uni-freiburg.de/post/transform-pdf-timetables-into-gtfs/),
which describes the previously used table extraction
and provides a shorter overview on how pdf2gtfs works.


## Bugs and suggestions

If something is not working or is missing, feel free to create an issue.


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
