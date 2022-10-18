---
title: "Transform PDF timetables into GTFS"
date: 2022-09-29T13:13:22+02:00
author: "Julius Heinzinger"
authorAvatar: "img/ada.jpg"
tags: [QLever]
categories: [project]
image: ""
draft: true
---

Extracting the schedule data from PDF timetables is a problem,
which prevents the easy use of otherwise available schedule data.\
Though many GTFS feeds already exist, either on their transit agencies
website or in some database, this python project aims to enable the
extraction of this data, when such feeds are not available.\
It also uses [QLever](https://github.com/ad-freiburg/qlever)
to query [OpenStreetMap](https://www.openstreetmap.org/), in order
to find the coordinates of each stop.

# Contents

1. [Introduction](#1-introduction)
    1. [GTFS](#11-gtfs)
    2. [OpenStreetMap and QLever](#12-openstreetmap-and-qlever)
2. [Implementation](#2-implementation)
    1. [Extracting timetable data](#21-extracting-timetable-data)
    2. [Creating GTFS](#22-creating-the-gtfs-files-in-memory)
    3. [Finding stop locations](#23-finding-stop-locations)
3. [Configuration](#3-configuration)
4. [Validation and testing](#4-validation-and-testing)
5. [Conclusion](#5-conclusion)
6. [Future plans](#6-future-plans)
    1. [Multi-line stopnames](#61-multi-line-stopnames)
    2. [Integrity checks](#62-integrity-checks)
    3. [Support for different timetables](#63-supporting-differently-styled-timetables)
    4. [Rotated stopnames](#64-rotated-stopnames)
    5. [Font based context](#65-font-based-context)
    6. [Increase/improve usage of QLever](#66-increaseimprove-usage-of-qlever)
    7. [Allow other services than QLever + OSM](#67-allow-other-services-than-qlever--osm)

# 1. Introduction

The goal of this project is to create a tool which takes a PDF file containing
timetables such as the one shown in the image below and output the schedule data
as a valid GTFS feed. As is required by the GTFS, it has to be able to locate the
coordinates of the stops used in the input file.\
It should also be easily reproducable, thoroughly tested and, as additional personal
requirements, highly configurable and as independent from online services as possible.

<div id="vag_linie_1">
![VAG Linie 1][vag_linie_1]
</div>

> Note: Boxes like this one are used to offer some useful tips or implementation details.

### PDF

PDF files generally do not contain their text in human readable form. Instead they use a
layout-based system, where each character's position is defined using a bounding box.
This results in some difficulty in extracting text, especially, if the context of the
texts position matters.

### 1.1. GTFS

As the name implies, the general transit feed specification
([GTFS](https://developers.google.com/transit/gtfs/reference)) specifies a general
format, in which transit information can be stored in a so called 'feed'. A feed
is simply a zip-archive of csv-files (with .txt extension). The format of each
csv-file is defined by the specification.\
Given a GTFS feed, one can for example display the routes of the feed in a map or
create a trip planner.\
Multiple services, such as the
[Mobility Database](https://database.mobilitydata.org/) exist, which already provide
a large number of feeds for different countries and transportation methods.
As stated above, the goal of this project is to fill the gap of timetables, which are
not published in a GTFS feed, but in a PDF (usually used for print) and considering
the ever-changing nature of these timetables, manual extraction is not feasible.\
GTFS is the de-facto standard for transit data, so exporting it in this format
makes sense.

[//]: # (Just using shell here, to add some highlighting)

#### GTFS example

This example shows a small (and truncated) excerpt of some GTFS files.
The exact format for each file can be found
[here](https://developers.google.com/transit/gtfs/reference#dataset_files).

- `stops.txt` contains all information about the stops, including their location
- `routes.txt` contains the name and type (here: Tram) for a route
- `calendar.txt` contains between which start-/end-date and at which days service is active
- `trips.txt` maps routes to service days. Here, the trip with id "26" occurs on weekdays
  with route described in `routes.txt`
- `stop_times.txt` contains the exact times, at which the trip is supposed to
  arrive from and depart to each stop

```shell
$ cat stops.txt
stop_id,stop_name,stop_lat,stop_lon
"1","Laßbergstraße",47.98458,7.89367
"2","Römerhof",47.98618,7.88849
...
"23","Moosweiher",48.02875,7.80893

$ cat routes.txt
route_id,agency_id,route_short_name,route_long_name,route_type
"24","0",,"Laßbergstraße-Moosweiher",1

$ cat calendar.txt
service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date
"25",1,1,1,1,1,0,0,"20220101","20221231"

$ cat trips.txt
trip_id,route_id,service_id
"26","24","25"

$ head -3 stop_times.txt
trip_id,arrival_time,departure_time,stop_id,stop_sequence
"26",05:17:00,05:17:00,"1",0
"26",05:18:00,05:18:00,"2",1
...
"26",05:48:00,05:48:00,"23",22
```

### 1.2. OpenStreetMap and QLever

wääää
[OpenStreetMap](https://www.openstreetmap.org/) provides map data, including information
about public transport, from all over the world and is maintained by an active community.

[QLever](https://github.com/ad-freiburg/qlever) is a SPARQL engine created by the
[Chair for Algorithms and Data Structures](https://ad.cs.uni-freiburg.de/), which can be
used to query OpenStreetMap.

@@@@@ OSMKEY section

# 2. Implementation

The problem of getting from a timetable in a PDF to a valid GTFS feed, can roughly be
split into three sub-problems. First, we extract the data from the input file.
Then, we create the GTFS files using the schedule data, in memory(?).
Lastly, we search for the stop locations and, after adding the stop locations to the stops file,
we create a the zip-archive and write it to disk.

## 2.1 Extracting timetable data

In the first step we read the PDF file and create one TimeTable object for
each timetable in the pdf. Each TimeTable will contain all necessary information
to perform the remaining steps for the specific timetable it was created from.

### Remove unneccessary information

Before we extract anything however, we first preprocess the input file using
[ghostscript](https://www.ghostscript.com/). The important options used are
`-dFILTERIMAGE` and `-dFILTERVECTOR`, which remove all images and vector graphics
from the PDF respectively. Without the preprocessing, the actual extraction
of the text, would take considerably longer.

Another, in our case welcome, side-effect of the preprocessing is the removal of
artifacts, i.e. invisible timetables. Essentially, some PDFs used during
development have the issue, that most pages also contain tables of other pages.
These are not visible in a PDF viewer, but would overlap with the visible tables
and were readable by the libraries we used.
This invisible text is removed during preprocessing, though it's unclear why
it is removed, i.e. which option of ghostscript is causing it.\
As a side-note, even simply using
`gs -sDEVICE=pdfwrite -dNOPAUSE -dBATCH -sOutputFile=output.pdf input.pdf`
would result in the removal of these artifacts, so we assume it is either a
bug in ghostscript
(like [this similar bug](https://bugs.ghostscript.com/show_bug.cgi?id=705187))
or (more likely) some of the default options of ghostscript's `pdfwrite` have this effect.
> As this may cause some, possibly good, data to be removed,
> preprocessing can be disabled with `--no-preprocess`.

### Extract the characters

To extract all text characters, we use
[pdfminer.six](https://pdfminersix.readthedocs.io/en/latest/)
and store them in a [pandas](https://pandas.pydata.org/) `DataFrame`.
The [advanced layout analysis][la_params] of pdfminer,
i.e. the detection of words and textlines, has been disabled, because it
would sometimes result in some of the necessary context being lost.
In particular, given the example timetable below, the annotation row would
loose the vertical coordinate context of the annotations.
The line would simply read "VERKEHRSHINWEIS V s". Later assignment
of the "V" and "s" to a specific column would not be possible.\
At this point, the DataFrame contains the text, coordinates and rotation of each
character of the PDF.

![Advanced layout analysis example][ala_linie_1]

### Datastructure layout

The basic layout of the created datastructures looks like this:
![Datastructure layout][datastructure_layout]
In the upper part, the creation order is shown, i.e. first the Chars are created,
then the Fields

Each TimeTableEntry maps Stops to the time strings of the

### Character, Char and BBox

wäää
A character is a single letter and a `Char` is an object, which describes
the position, character and orientation of a single character in the pdf.

The `BBox` contains the coordinates of the top-left and bottom-right corners of the
rectangle, that fully encloses an object, such as a `Char`, `Field`, `Row` or `Column`.\
It also provides different methods, most notably the `is_close()` method, which
is used to determine whether two bounding boxes have negliable distance between
them (or touch). The BBoxObject is a simple wrapper, subclassed by all objects,
that have a BBox.
> The origin of the coordinates, used in the BBox, differs from the ones
> used in the PDF. While the origin in PDFs is the bottom-left corner, our
> datastructures use the top-left corner.

### DataFrame to TimeTable

@@@
Turning the DataFrame into TimeTables works in two stages:\
In the first stage, we create PDFTables. Their purpose is essentially,
to divide each page of the PDF into its respective tables.\
In the second stage, each PDFTable is transformed into a TimeTable. TimeTables
are "farther away" from the input, i.e. they have no knowledge about the particular
positions of each character, but instead contain a list of Stops and TimeTableEntrys.

This diagram, shows roughly the relationship between the main datastructures we created:

![Datastructure layout][datastructure_layout]

To put simply, a PDFTable has both Rows and Columns, which both consist of Fields
and Fields are a combination of Chars. Finally, all Rows, Columns, Fields
and PDFTables are BBoxObjects. The TimeTable consists of a single StopList,
containing all Stops of the TimeTable, and at least one TimeTableEntry.

#### Types of Fields, Rows and Columns

Each of the objects Row, Column and Field have their own type, which is
later used, e.g. to detect which columns contain information about stops or
whether a stop describes a vehicles arrival or its departure.
For example Field objects are of type `DataField`, if they contain data that can be parsed
by `strftime()` using the given time_format. A Row/Column on the other hand is of type
`DataRow`/`DataColumn` respectively, if any of its fields is of type `DataField`.

#### PDFTable

As stated above, the purpose of PDFTables is to split the PDF into its tables.
This includes splitting *and* merging tables, depending on the number of
Rows/Columns with a specific type.\
For example, each PDFTable should have only a single HeaderRow
and a single StopColumn. If not, it will be split into multiple PDFTables.
In the same way, if there are two PDFTable `P1` and `P2`, and `P2` does not
have a HeaderRow, then the `P2` is merged into `P1`.

To create the PDFTables, we first need to create the Fields, Rows and Columns.
A Field is a continuous stream of characters, on the same line.
That means that each characters `x0` coordinate is close to the previous ones `x1`
coordinate (continuous) and each character of the Field has the same `y0/y1`
coordinates (same line).
So, in order to create the Fields, we basically need to (stably) sort the DataFrame
first by the `x0` coordinate, to ensure the correct horizontal order of characters,
and then by the `y0` coordinate, to easily iterate over all characters of a single line.

Now we can create the Fields like this:

1. Create a Field from the current char.
2. Select the next char in the DataFrame if it exists, otherwise we are done.
3. If the current char is on the same line and the current char's BBox
   is close to the fields BBox, add the char to the Field and go to step 2.
   Otherwise, go to step 1.

Next, the Fields are grouped into Rows depending on which line they are on.
After determining the type of Fields and Rows based on their respective contents,
the Columns are created using the coordinates and types of both Rows and Fields.
One important thing to note is, that Columns do not contain Fields from Rows
of type HeaderRow or Other. The reasoning for this is, that Rows of type Other,
do not contain any information, that we can process (currently) and each Field
in a HeaderRow usually spans multiple columns in a table. Therefore only Rows
containing data, annotations or route information are put into Columns.

As the final step, the above mentioned splitting and merging takes place, until
each PDFTable contains only a single HeaderRow and a single StopRow. This also
includes, that the type of both Rows and Columns is reevaluated, in case the
process altered their contents in a way that would affect their types.

Now we have extracted all data from the PDF and turned it into PDFTables.

### PDFTable to TimeTable

The difference between TimeTable and PDFTable is the (abstract) distance to
the actual pdf.
While a PDFTable holds all coordinate information about every Field,
Row and Column, a TimeTable consists of multiple TimeTableEntry and a
single StopList. The StopList basically contains information about the
StopFields of the corresponding PDFTable and
each TimeTableEntry maps information about the arrival/departure of a single
DataColumn to the respective Stops.

#### StopList

As the name implies, a StopList is a list of Stops. As a PDFTable may have the
same stop occurring multiple times, each Stop can also have an annotation,
showing whether this stop describes the arrival or departure of the transport vehicle.
Further, each stop has a property `is_connection` which will be explained later.

#### Stops as connections

Sometimes, some Stops in the PDFTable are not actual stops that will be served, but
instead show frequently used connections from the previous Stop. For example in
the figure below, the italized Stops show a different trip to the airport in Frankfurt.
These connections exist for convenience of the user of the PDF timetable,
but for us this is more of an inconvenience, because we need to detect and ignore them.

![Example of a connection in a PDF timetable][connection_example]

The detection of these connections works by simply checking for reoccurring Stops
with alternating arrival/departure identifier. In the example above this would
detect the two italized Stops as connections, simply because before and after them
the same Stop occurrs. Using the config files, you can decide, how many connection
Stops are necessary for them to be ignored, or disable the detection completely.

#### TimeTableEntry

Each TimeTableEntry contains the information of a single trip. This includes the
days the trip occurs, any annotations and route information of this trip,
and a map between Stops and the time strings (e.g. "12:30").

#### TimeTable

Turning a PDFTable into a TimeTable is pretty straight-forward. First, the
Column with type StopColumn is used to create the StopList. Then, the Columns
of the PDFTable are iterated over, creating a TimeTableEntry for each of them.
Finally the Stops that are connections are determined and the TimeTable is
ready to use for next step.

## 2.2. Creating the GTFS files in memory

Before trying to find the stop locations, we first combine all information
we have accumulated so far into different datastructures, each of which mirrors
a specific GTFS file.\
For example, the datastructure `Routes` contains all the necessary information
to create a valid [routes.txt](https://developers.google.com/transit/gtfs/reference#routestxt).
`StopTimes` on the other hand, contains all necessary information to create a valid
[stop_times.txt](https://developers.google.com/transit/gtfs/reference#stop_timestxt),
and so on and so forth.
The only exception to this is `Stops`, which does not contain valid locations, yet.
Roughly that is already all there is to this step, there are some caveats and
special cases however, showcased here.

### ID generation

The ID's used in some GTFS-files (e.g. `agency_id` in `agency.txt`) are generated
to be globally (i.e. in this GTFS-feed) unique. For simplicity, they were chosen
to be integers (casted to string, as required by the specification). If an ID is
already used by some existing GTFS-file, it will not be used.

### Repeating stop times

If a trip is repeated every X minutes, the transit agency oftentimes
uses what we call repeated columns. In the figure below is an example of such a column.

<img src="/img/project-transform-timetables-into-gtfs/repeat_column.png" height="300" />

When transforming a `TimeTable` into GTFS files, these columns are expanded,
i.e. when encountering a stop_times entry, which contains a (user-specified) repeat-identifier,
we first create the next entry and afterwards fill in the remaining values shifted
by the given amount.

For example, given a `TimeTable` like the one above, the important entries
for adding all repeated stop times are the first, second and third entries.
The first one marks the lower bound, from which to add the repeating stop times.
The amount that each new entry will need to be shifted by is taken from the second entry,
the actual repeat entry. The third entry marks the upper bound.\
After creating the stop times for the second and fourth entry,
we iteratively create new stop times, each being shifted by the number of minutes,
until we reach the upper bound, at which point we stop and go to the next entry.

### Existing GTFS-files

Before creating either the `agency.txt` or the `stops.txt`, the output directory
is checked for those those files. If either exists, it will be used to
select an agency or to provide the stops, respectively. In case only some stops can be
found in the `stops.txt`, they will be used as fix points for the location
detection. This means even if another possible combination of locations would be better,
it will not be used if it does not use the existing stops.\
All other GTFS-files are overwritten (based on the configuration), should they exist.

### Holidays and other special dates

Using the [holidays](https://pypi.org/project/holidays/)
library, we can specify both a country and state/canton/etc., to detect the
dates of country-/statewide holidays and adjust the stop times on these dates.

Also, using the command line interface, the user is able to define dates, at which
service differs from the usual schedule, which applies to all columns with a
specific annotation (e.g. `s` or `V` in the figure below).

![Figure showing route annotations][annotations]

## 2.3. Finding stop locations

The final step consists of getting publicly available location data and using this data along
with the information about the routes we have from the pdf, most notably the duration it
takes to get from one stop to the next, and which stops are connected into a route.
This is also the reason, why we create the GTFS files first, because it makes getting this
information so much easier.

Luckily all the necessary data can be found in [OpenStreetMap](https://www.openstreetmap.org/),
which can be easily queried using for example [QLever](https://github.com/ad-freiburg/qlever).

### Fetching the data

When first running pdf2gtfs or when the local cache is not used, the OSM data
is fetched using QLever.
In that case, a query is created, using ....

#### OSMKeys

@@@ maybe move to introduction
Each node in OpenStreetMap can have different osmkey:value pairs, which describe the node.
For example, the `name`-key provides the primary name used for a particular node.
However, there exist keys, like `alt_name` or `ref_name`, which can be used to provide
alternative names, as well. The key `ref_name` in particular is used to "specify the
unique human-readable name used in an external data management system
(e.g. timetables/schedules)"<sup>\[2\]</sup>. There are a lot more osmkeys, that
are used to describe the node in more detail. The ones used during the location detection
are described in the next subsection.

#### The DataFrame

After executing the query on QLever, we have a DataFrame, with the following columns:

- lat/lon: The latitude and longitude of the node
- names - A "|" separated list of different names,
  in particular `name`, `alt_name` and `ref_name`
- A collection of different osmkeys (like "railway", "bus", "tram", etc.)

### Normalizing names

After the data has been fetched, it will be normalized and,
if the caching is enabled, cached on the local filesystem afterwards.

###### Fixing abbreviations

Because some stop names can be quite long, they are often abbreviated in the PDF
in some way.
Using the user-configured abbreviations dictionary, all abbreviations are
expanded to their full form (e.g. "Frankfurt Hbf" for "Frankfurt Hauptbahnhof").\
There are some caveats, to when abbreviations are extended.
See the [default configuration]() for more info.

###### Removal of parentheses and symbols

Any parentheses, as well as their contents are removed from each name,
Any character of the stop names, that is not a normal (i.e. latin) letter, number
or the pipe symbol ("|") is removed from the name.

###### Casefolding and lowering

Some letters can be written in different ways,
e.g. "Laßbergstraße" and "Lassbergstrasse", even though they describe the same stop.
the names are casefolded, resulting in the latter version of the example.\
All names are also converted to lower case, for the exact same reason.

###### Cache

After the normalization, the DataFrame will be saved to the cache directory
(`~/.cache/pdf2gtfs/` or `%LOCALAPPDATA%/pdf2gtfs/` under Linux
and Windows respectively). The cache not only includes the data, but the date of
fetching, the query and the used abbreviations dictionary, as well.
This is to ensure, that the data is fetched again, if either the query or
the abbreviations dictionary are changed.
> The data is fetched again as well, if the cache is too old (default: 7 days).

### Preparing the DataFrame

Once the DataFrame is ready, we filter all entries in the DataFrame,
which do not contain any (normalized) stop name or its permutations in their
names column, using a regular expression
(e.g. ```berlin hauptbahnhof|hauptbahnhof berlin|...```).

The DF also gets new columns:

* `stop_id`: identifier for the stop, which is contained in the names column
* `node_cost`: the raw costs of the node based on the selected route type
* `name_cost`: the edit distance between any of the names and the actual
  (and sanitized) stop name

These are not added to the cache, because they depend solely on the
stops of the current input file.

###### Calculating the node cost

As stated above, each node on OpenStreetMap, contains one or more
key-value-pairs, which specify its function or give some additional information.
The cost of a specific node is calculated for the specified `routetype` using a simple map.
For example, the `railway`-key can be set to, among others, `station`, `halt`
and `tram_stop`. The `tram`-key can be set to `yes` and `no`.\
If the routetype is 'Tram', the cost of a node with
`railway=halt` will be higher than the cost of a node with the `railway=tram_stop`
or `tram=yes`. A node without any matching key-value-pairs will have even
higher cost, while a node with `tram=no` will not be considered at all.

###### Calculating the name cost

To get the name cost, we simply need calculate the edit-distance between
the stop name and the name for the node, and apply a function, which punishes lower
edit-distances significantly less than larger ones. We do this, to ensure that two nodes
`N1` and `N2`, with similar edit-distance to the stop name, have the same name cost.
Thus, only node cost and travel cost influence the decision which node is better.

### Finding the best locations

The detection of the best combination of locations can be specified as a
shortest path problem in a directed graph.
For this, every possible location is a node and each node `N1` is connected with
a directed edge, with weight `T`, to another node `N2`, iff `N1` is a node
for the preceeding stop of `N2`. `T` is defined as the sum of the
node-, name- and travel cost of the target node `N2`.
We use Dijkstra's algorithm to find the shortest path.

###### Impossible neighbors

To reduce the number of exact distance calculations, which are expensive
computatiponally, when updating the neighbors of a node `N`, we first filter the
neighbors by their rough distance. For example, it makes no sense, that a bus
travels 100km in 3 minutes. Therefore, given the time it takes to travel from
one stop to the next and the user-specified average speed of the vehicle,
we only pay attention to neighboring nodes, that are closer than the
maximum expected distance.\
To put simply, we draw a square of size `s` with `N` at its center, and only
calculate the distance to neighbors within that square. The size `s` is
defined as `2 * max_expected_distance`.

For that, we use the following two formulas to calculate the approximate distance
depending on the difference in latitude and longitude:
$$\text{lat distance} = 111.34 * \delta lat_d$$
$$\text{lon distance} = 111.34 * |\cos{\delta lat_m}| * \delta lon_d$$
where lat<sub>d</sub> and lon<sub>d</sub> are the difference in latitude/longitude
respectively and lat<sub>m</sub> is the latitude of the midpoint.
The reason we need the cosine of the latitude, is that the longitude distance
changes, depending on the latitude.\
The above formulas are approximations, but are good enough, to determine if two
locations are somewhere close to each other. Most importantly, they are a lot faster
than calculating the exact distance (which is done using
[geopy](https://geopy.readthedocs.io/en/stable/)).

###### Handling missing locations

Because we only filter the locations based on the stop names, it can happen,
that the location of a stop could not be found. In such a case a `MissingNode` is
used, to still enable the location detection for the other stops. Missing nodes have
a very high node cost, to ensure that existing nodes with high travel cost are
preferred. During display of the nodes (and if `--include-missing` is given), the
location of the missing nodes is interpolated, using the surrounding existing nodes.

# 3. Configuration

Most of the program is configurable by creating configuration files or, for frequently
used options, using the available command line arguments.
This includes (a full list/description can be found in the default configuration):

- `max_row_distance`: The maximum distance between two rows, for them to be considered part
  of the same table.
- `time_format`: The format used by the given times. Can be any string supported by
  [strftime](https://docs.python.org/3/library/datetime.html#datetime.datetime.strftime).
- `average_speed`: The average speed of the transportation vehicle
- `arrival_identifier/departure_identifier`: Text used in the column following the
  stops, to identify if the vehicle arrives or departs at the specified times.

If a timetable was not read properly, or the detected locations contain many
missing nodes, adjusting these options may help.

# 4. Validation and testing

### Validation of the GTFS output

Validation of the GTFS feed has been done using
[gtfs-validator](https://github.com/MobilityData/gtfs-validator).
Apart from

### Testing

...

# 5. Conclusion

The program fulfills the project requirements. However, more work needs to be done,
in particular to improve the support for different timetable formats.

æææ
At the same time, the average distance between the locations, that were found,
and the actual location is less than 100m. That holds true at least for the,
admittedly small, number of input pdfs used during development (CoNFIrmatION BiAS?!?!).
æææ

Some input pdfs could not be read properly, æææ for example this
[SEE FIGURE](figure badexample). The problem æææ
This occurs, when the input pdf uses a format, which is not recognized
(see [future plans](#supporting-differently-styled-timetables)), or if the
chosen options do not adhere to the (observed) requirements of the format.
For example, setting `min_row_count = 10`, if the timetables only contain 8 rows.

Some locations were not found by pdf2gtfs, even if they actually exist on OSM.
This is due both to the manner the dataset is filtered (i.e. using the stop name),
and the fact that some of the transit agency names differ from the names used in OSM.

<figure id="figure_osm_heatmap">
    <img src="/img/project-transform-timetables-into-gtfs/osm_comparison.png"
     alt="Heatmap of the whole world showing possible stop locations" style="width:100%">
    <figcaption style="font-size: 12px">
    Figure x: Heatmap of OSM nodes, that have the key public_transport set to one of
    "stop_position", "platform" or "station"<sup>[1]</sup>
    </figcaption>
</figure>

During development, focus laid on german transit agencies, meaning the location
detection (obviously) used the OSM data for Germany.
However, as seen in the [heatmap](#figure_osm_heatmap), the density of available,
useful data in Germany (and europe in general) is a lot higher than in most other countries.
In other words, depending on country
(and probably population density, as well), the results may be worse than displayed here.

The full evaluation of pdf2gtfs will be the topic of my bachelor's thesis.

# 6. Future plans

## 6.1 Multi-line stopnames

Currently the tables are read line for line, and every line of a single table has unique
y-coordinates. To properly detect and support stops spanning multiple lines,
one possible implementation would be to simply merge stop columns, such that each field
in the column is merged with the next one, iff the fields row does not contain any data fields.
However this approach does come at the cost of only supporting those multi-line-stops,
where the first row of each stop contains data fields. If the data is centered vertically
instead, this implementation would result in incorrect stop names.

æ Possible implementation. + image? +
@@@ Add new config key `multiline_stop_strategy=None|center|top|bot`

## 6.2 Integrity checks

The time data from the tables is checked for neither continuity nor monotony æcheckæ.
This may result in

æ this would help how? What do we do with tables where this happens?
æ also: how does this even happen?

## 6.3 Supporting differently styled timetables

Timetables using columns to display the stops, i.e. the stops are on the top of the table
and the stop times are written left to right, are unsupported. This style is widely used in
in North America. One possible approach to support this style would be to simply transpose
either the `DataFrame` or the `PDFTable`.

## 6.4 Rotated stopnames

Another problem that often occurs with transposed timetables, is the existence
of rotated characters. While in the normal style, where every line is a stop and
columns are routes, the number of stops can be onsiderably high, for
the transposed style the number of stops is limited by the length of the stop names
and width of the page.\
To mitigate this and allow for longer routes, the characters/stops are typically
written at an angle (usually between 30 and 90 degrees).
To enable extraction of tables with rotated stopnames, we need to first detect their
position. Afterwards, given the rotated characters and the calculated angle,
we can reconstruct the actual stop name.

## 6.5 Font-based context

Currently all characters in the pdf are treated the same way, regardless of their
font-properties (e.g. size, bold, italic, ...). To support timetables such as these,
more work needs to be done in regards to properly detecting the properties, and
giving the user some (simple) way of applying meaning to each property.

For example, some timetables in the USA use bold stop times, to indicate PM times.
However, we first need to check if there is actually a wide range of
varying usage of these properties. Otherwise, adding more config-options
(e.g. `bold_times_indicate_pm`/etc.), each handling a single context usage,
would probably be the simplest solution to support this type of timetable.

## 6.6 Increase/improve usage of QLever

We can probably improve the query to QLever, to get more key:value-pairs
in order to improve the node cost function. For example, OSM has multiple GTFS-related
keys, which would not only improve the stop-to-location-matching, but could provide
additional information like the official stop_id as well.\
Alternatively we could use QLever to perform the first, rough filter-step,
leveraging its speed.
However, considering the cache will not be usable, because the first filter step
depends on the given stops, more testing is required to determine if,
and how much the performance is expected to increase, if this was implemented.

## 6.7 Allow other services than QLever + OSM

As mentioned before, one caveat is that OSM contains exceptional amounts of information,
when it comes to Germany. In other countries, the number of different stop locations
may be a lot æ@æ@æ lower. In such cases, usage of other services which provide some
interface to retrieve the stop locations as well as the necessary metadata, could prove
essential to further improve the performance of the location detection.

### Allow multiple input files

In case the user has a lot of pdfs, for example for every bus route of a single agency,
it makes sense to output all information in a single GTFS feed. Currently this is not
possible. Before implementing, further testing needs to be done, to ensure
that the program state after processing one pdf does not alter the output of processing another.

# A

TODO: Stop cost

TODO: Why use df to check for locations if we already have created all nodes?!

images:

[vag_linie_1]: /img/project-transform-timetables-into-gtfs/vag_1_table_1.png

[osm_comparison]: /img/project-transform-timetables-into-gtfs/osm_comparison.png

[datastructure_layout]: /img/project-transform-timetables-into-gtfs/layout_datastructures.png

[ala_linie_1]: /img/project-transform-timetables-into-gtfs/ala_linie_1.png

[connection_example]: /img/project-transform-timetables-into-gtfs/connection.png

[repeat_column]: /img/project-transform-timetables-into-gtfs/repeat_column.png

[annotations]: /img/project-transform-timetables-into-gtfs/annotations.png

links:

[la_params]: hhttps://wiki.openstreetmap.org/wiki/Key:ref_namettps://pdfminersix.readthedocs.io/en/latest/reference/composable.html#api-laparams

Sources:\
\[1\]: Displayed using QLever's map view++ on this
[query](https://qlever.cs.uni-freiburg.de/osm-planet/?query=PREFIX+geo%3A+%3Chttp%3A%2F%2Fwww.opengis.net%2Font%2Fgeosparql%23%3E%0APREFIX+osm%3A+%3Chttps%3A%2F%2Fwww.openstreetmap.org%2F%3E%0APREFIX+rdf%3A+%3Chttp%3A%2F%2Fwww.w3.org%2F1999%2F02%2F22-rdf-syntax-ns%23%3E%0APREFIX+osmkey%3A+%3Chttps%3A%2F%2Fwww.openstreetmap.org%2Fwiki%2FKey%3A%3E%0ASELECT+%3Fstop+%3Fstop_loc+WHERE+%7B%0A++%7B+%3Fstop+osmkey%3Apublic_transport+%22stop_position%22+.+%7D+UNION+%7B+%7B+%3Fstop+osmkey%3Apublic_transport+%22platform%22+.+%7D+UNION+%7B+%3Fstop+osmkey%3Apublic_transport+%22station%22+.+%7D%0A+%7D%0A++%3Fstop+rdf%3Atype+osm%3Anode+.%0A++%3Fstop+geo%3AhasGeometry+%3Fstop_loc%0A%7D)
\[2\]: https://wiki.openstreetmap.org/wiki/Key:ref_name

aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
As every transit agency has their own timetable format, the main difficulty,
during extraction, is to create a extraction function, which is able to read a
wide variety of timetable formats.\
aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa

