---
title: "Transform PDF timetables into GTFS"
date: 2022-09-29T13:13:22+02:00
author: "Julius Heinzinger"
authorAvatar: ""
tags: [python, GTFS, pdf, timetable]
categories: [project]
image: "/img/project-transform-timetables-into-gtfs/title.png"
draft: true
---

The current inability to extract the schedule data from PDF timetables,
prevents the easy use of this otherwise available data.\
Though many GTFS feeds already exist, either on their transit agencies
website or in some database, this python project aims to enable the
extraction of this data, when such feeds are not available.

<!--more-->

# Contents

1. [Introduction](#1-introduction)
2. [Implementation](#2-implementation)
    1. [Extracting timetable data](#21-extracting-timetable-data)
    2. [Creating GTFS](#22-creating-the-gtfs-files-in-memory)
    3. [Finding stop locations](#23-finding-stop-locations)
3. [Configuration](#3-configuration)
4. [Evaluation](#4-evaluation)
5. [Conclusion and future plans](#5-conclusion-and-future-plans)

# 1. Introduction

The goal of this project is to create a tool, namely pdf2gtfs, which takes a
PDF file containing timetables such as the one shown in the figure below
([complete file](https://www.vag-freiburg.de/fileadmin/vag_freiburg_media/downloads/linienplaene/Linie_01.pdf))
and
output the schedule data as a valid GTFS feed. As is required by the GTFS,
it has to be able to locate the coordinates of the stops used in the input file.\
It should also be easily reproducable, thoroughly tested and, as additional personal
requirements, highly configurable and as independent from online services as possible.

![VAG Linie 1][vag_linie_1]

### GTFS

As the name implies, the general transit feed specification
([GTFS](https://developers.google.com/transit/gtfs/reference)) specifies a general
format, in which transit information can be stored in a so called 'feed'. A feed
is simply a zip-archive of CSV-files (with .txt extension). The format of each
CSV-file is defined by the specification. Considering GTFS is the de-facto
standard for transit data, exporting it in this format makes sense, as well.\
Given a GTFS feed, one can for example display the routes of the feed in a map or
create a trip planner. Multiple services, such as the
[Mobility Database](https://database.mobilitydata.org/), exist, which already provide
a large number of feeds for different countries and transportation methods.
As stated above, the goal of this project is to fill the gap of timetables,
which are not published in a GTFS feed, but in a PDF (usually used for print)
and considering the ever-changing nature of these timetables,
manual extraction is not feasible.

###### GTFS example

This example shows a small (and truncated) excerpt of a very simple GTFS feed.
The exact format for each file can be found
[here](https://developers.google.com/transit/gtfs/reference#dataset_files).

- `stops.txt` contains the name and location of the stops
- `routes.txt` contains the name and type (here: 1 for "Tram") for a route
- `calendar.txt` defines, between which start-/end-date and at which days
  service is active
- `trips.txt` maps routes to service days. Here, the trip with id "26"
  occurs Monday to Friday, with the route 'Laßbergstraße-Moosweiher'
  described in `routes.txt`
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

$ cat stop_times.txt
trip_id,arrival_time,departure_time,stop_id,stop_sequence
"26",05:17:00,05:17:00,"1",0
"26",05:18:00,05:18:00,"2",1
...
"26",05:48:00,05:48:00,"23",22
```

### OpenStreetMap

We use data from
[OpenStreetMap](https://www.openstreetmap.org/) (OSM), to search for the locations of
the stops and to decide, which location fits best.\
We query OSM using [QLever](https://github.com/ad-freiburg/qlever), a super-fast SPARQL
engine, which was developed at the
[Chair for Algorithms and Data Structures](https://ad.cs.uni-freiburg.de/).

OpenStreetMap consists of nodes (and some other types, we don't use), which
describe an object or a point of interest at a specific location.
Each node can have different key-value pairs, which further describe it.\
For example, the `name` key provides the primary name used for a particular node.
At the same time, there exist keys like `alt_name` or `ref_name`,
which can be used to provide alternative names.
The key `ref_name` in particular, is used to "specify the
unique human-readable name used in an external data management system
(e.g. timetables/schedules)"<sup>\[2\]</sup>.\
For public transport there exist for example the `railway`, `tram` or `bus` keys,
each used to describe (using the value) how the node is related to the given key.

# 2. Implementation

The problem of getting from a timetable in a PDF to a valid GTFS feed, can roughly be
split into three sub-problems. First, we extract the data from the input file.
Next, using the schedule data, we create the GTFS files in memory.
Lastly, we search for the stop locations and, after adding the stop
locations to the stops file, we create the zip-archive and write it to disk.

## 2.1 Extracting timetable data

In the first step we read the PDF file and create one TimeTable object for
each timetable in the PDF. Each TimeTable will contain all necessary information
to perform the remaining steps for the specific timetable it was created from.

### Remove unneccessary information

Before we extract anything however, we first preprocess the input file using
[ghostscript](https://www.ghostscript.com/). The important options used are
`-dFILTERIMAGE` and `-dFILTERVECTOR`, which remove all images and vector graphics
from the PDF respectively. Without the preprocessing, the actual extraction
of the text, would take considerably (minutes vs. less than a second) longer.

Another, in our case welcome, side-effect of the preprocessing is the removal of
some artifacts, i.e. invisible timetables. Essentially, some PDFs used during
development have the issue, that most pages also contain tables of other pages.
These are not visible in a PDF viewer, but overlap with the visible tables
and are readable by the libraries we use.
This invisible text is removed during preprocessing, though it's unclear,
which option of ghostscript is causing it.\
In particular, even simply using
`gs -sDEVICE=pdfwrite -sOutputFile=output.pdf input.pdf`
would result in the removal of these artifacts. So, we assume it is either a
bug in ghostscript
(like [this similar bug](https://bugs.ghostscript.com/show_bug.cgi?id=705187))
or (more likely) some of the default options of ghostscript's `pdfwrite`
have this effect.
> As this may cause some possibly good data to be removed,
> preprocessing can be disabled using `--no-preprocess`.

### Extract the characters

PDF files generally do not contain their text in human readable form.
Instead they use a layout-based system, where each character's position
is defined using a bounding box.

To extract all text characters, along with their bounding boxes and rotation,
we use [pdfminer.six](https://pdfminersix.readthedocs.io/en/latest/).
The [advanced layout analysis][la_params] of pdfminer,
i.e. the detection of words and textlines, has been disabled, because it
would sometimes result in some of the necessary context being lost.\
In particular, given the example timetable below, the annotation (the second)
row would loose the vertical coordinate context of the annotations.
The line would simply read "VERKEHRSHINWEIS V s". Later assignment
of the "V" and "s" to a specific column would not be possible.

![Advanced layout analysis example][vag_linie_1]

After reading the PDF using pdfminer.six we store them in a
[pandas](https://pandas.pydata.org/) DataFrame.
It contains the text, coordinates and rotation of each character of the PDF.

### DataFrame to TimeTable

Turning the characters stored in the DataFrame into TimeTables works in two stages:\
In the first stage, we create PDFTables. Essentially, their purpose is
to divide each page of the PDF into its respective timetables.\
In the second stage, each PDFTable is transformed into a TimeTable.

This diagram roughly shows the relationship between the main datastructures we use:

![Datastructure layout][datastructure_layout]

To put simply, a PDFTable has Rows and Columns, which both consist of Fields,
and Fields are a combination of Chars. Additionally, all Rows, Columns, Fields
and PDFTables are BBoxObjects. This makes it easy to merge them and to check if
they are overlapping or close.\
The TimeTable consists of a single StopList,
containing all Stops of the TimeTable, and at least one TimeTableEntry, which
holds the information of a single trip (i.e. column).

###### BBox and BBoxObject

The BBox contains the coordinates of the top-left `(x0, y0)`
and bottom-right `(x1, y1)` corners of the
rectangle, that fully encloses an object, such as a Field, Row or Column.\
It also provides different methods, most notably the `is_close()` method, which
is used to determine whether two bounding boxes have negliable distance between
them (or touch). The BBoxObject is a simple wrapper, subclassed by all objects,
that have a BBox, to make e.g. merging of two BBoxObjects easier.
> The origin of the coordinates, used in the BBox, differs from the one
> used in the PDF. While the origin in PDFs is the bottom-left corner, our
> datastructures use the top-left corner.

###### Types of Fields, Rows and Columns

Each of the objects Row, Column and Field have their own type, which is
later used, e.g. to detect which columns contain information about stops or
whether a stop describes a vehicles arrival or its departure.\
For example, Field objects are of type DataField, if they contain data that can be parsed
by `strftime()` using the specified time format. A Row or Column, on the other hand,
is of type DataRow or DataColumn respectively, if any of its fields is
of type DataField. There is also the type OtherField/-Row/-Column, in case the
type could not be determined.

###### PDFTable

As stated above, the purpose of PDFTables is to split the PDF into its tables.
This includes both splitting *and* merging tables, depending on the number of
Rows/Columns with a specific type.\
For example, each PDFTable should have only a single HeaderRow
and a single StopColumn. If not, it will be split into multiple PDFTables.
In the same way, if there are two PDFTable `P1` and `P2`, and `P2` does not
have a HeaderRow, then the `P2` is merged into `P1`.

To create the PDFTables, we first need to create the Fields, Rows and Columns.
A Field is a continuous stream of characters on the same line.
What we mean by this is, that each character's left side `x0` (i.e. left)
coordinate is close to the previous one's `x1` (i.e. right) coordinate
(continuous) and each character of the Field has the same `y0` coordinates (same line).\
Essentially, in order to create the Fields, we sort the DataFrame
first by the `x0` coordinate, to ensure the correct horizontal order of characters,
and then sort (stably) by the `y0` coordinate, to easily iterate over all
characters of a single line.

Now we can create the Fields like this:

1. Create a Field from the current character.
2. Select the next character in the DataFrame if it exists, otherwise we are done.
3. If the current character is on the same line as the Field and the current
   character's BBox is close to the Field's BBox, add the char to the Field
   and go to step 2. Otherwise, go to step 1.

Next, the Fields are grouped into Rows depending on which line they are on.
After determining the type of Fields and Rows based on their respective contents,
the Columns are created using the coordinates and types of both Rows and Fields.\
One important thing to note is, that Columns do not contain Fields from Rows
of type HeaderRow or OtherRow. The reasoning for this is, that Rows of type
OtherRow do not contain any information, that we can process (currently, at least)
and that each Field in a HeaderRow usually spans multiple columns in a table.\
Therefore, only Rows containing time data, annotations or route information
are put into Columns. In the following figure, you can see the Fields (green),
Columns (red) and Rows (blue) visualized.

![field_col_row_visual][field_col_row_visual]

As the final step, the above mentioned splitting and merging takes place, until
each PDFTable contains only a single HeaderRow and a single StopColumn. This also
includes, that the type of both Rows and Columns is reevaluated, in case the
process altered their contents in a way that would affect their types.

Now we have extracted all data from the PDF and turned it into PDFTables.

### PDFTable to TimeTable

The difference between TimeTable and PDFTable is the (abstract) distance to
the actual PDF.
While a PDFTable holds all coordinate information about every Field,
Row and Column, a TimeTable only consists of multiple TimeTableEntry and a
single StopList.

As the name implies, a StopList is a list of Stops. As a PDFTable may have the
same stop occurring multiple times, each Stop can also have an annotation,
showing whether this stop describes the arrival or departure of the transport
vehicle.\
Each TimeTableEntry maps information about the arrival/departure of a single
DataColumn to the respective Stops. This includes the
days the trip occurs (taken from the HeaderRow),
any annotations and route information of this trip,
and a map between each Stop and the time strings (e.g. "12:30")
of the stop's Row.

###### Stops as connections

Sometimes, the timetable contains Stops that are not actual stops that will be served, but
instead show frequently-used connections from the previous Stop. For example in
the figure below, the italized Stops show a different trip to the airport in Frankfurt.
These connections exist for convenience of the user of the PDF timetable,
but for us this is more of an inconvenience, because we need to detect and ignore
them.

![Example of a connection in a PDF timetable][connection_example]

The detection of these connections works by simply checking for reoccurring Stops
with alternating arrival/departure identifier. In the example above this would
detect the two italized Stops as connections, simply because before and after them
the same Stop occurs, the one before having the arrival annotation and the one
after having the departure annotation.

###### TimeTable

Turning a PDFTable into a TimeTable is pretty straight-forward. First, the
Column with type StopColumn is used to create the StopList. Then, the other Columns
of the PDFTable are iterated over, creating a single TimeTableEntry for each of them.
Finally the Stops that are connections are determined and the TimeTable is
ready to use in the next step.

## 2.2. Creating the GTFS files in memory

Before trying to find the stop locations, we first combine all information
we have accumulated so far into different datastructures, each of which mirrors
a specific GTFS file.\
For example, the datastructure GTFSRoutes contains all the necessary information
to create a valid [routes.txt](https://developers.google.com/transit/gtfs/reference#routestxt).
GTFSStopTimes on the other hand, contains all necessary information to create a valid
[stop_times.txt](https://developers.google.com/transit/gtfs/reference#stop_timestxt),
and so on and so forth.
The only exception to this is GTFSStops, which does not contain any locations, yet.\
Roughly that is already all there is to this step, there are some caveats and
special cases however, which are showcased here.

### Existing GTFS-files

When creating either the GTFSAgency or the GTFSStops, the output directory
is checked for the corresponding `agency.txt` or `stops.txt` file.
If it exists, it will be used either to select an agency
or to provide the stops, respectively.\
In case only some stops can be
found in the `stops.txt`, they will be used as fix points for the location
detection. This means, even if another possible combination of locations would
appear to be better, it will not be used if it does not use the existing stops.

### ID generation

The IDs used in some GTFS files (e.g. `agency_id` in `agency.txt`) are generated
to be globally (i.e. in this GTFS feed) unique. For simplicity, they were chosen
to be integers (casted to string, as required by the specification). If an ID is
already used by some existing GTFS-file, it will not be used.

### Repeating stop times

If a trip is repeated every X minutes, the transit agency oftentimes
uses what we call repeated columns. In the figure below is an example of such
a column ("alle 6 Min.").

<img src="/img/project-transform-timetables-into-gtfs/repeat_column.png" height="300" />

When transforming a TimeTable into GTFS files, these columns are expanded,
i.e. when encountering a TimeTableEntry, which contains a (user-specified)
repeat identifier, we fill in the gap between the previous and next TimeTableEntry
with values shifted by the given amount.

For example, given a TimeTable like the one above, the entries required
for adding all repeated stop times are the first, second and third entries.
The first one marks the lower bound, the start, from which to add the repeating
stop times. The amount that each new entry will need to be shifted by is taken
from the second entry, the actual repeat entry.
The third entry marks the upper bound.\
We iteratively create new stop times, starting at the lower bound,
where each new entry is being shifted by the number of minutes,
until we reach the upper bound, at which point we are done.

### Holidays and other special dates

Using the [holidays](https://pypi.org/project/holidays/)
library, we can specify both a country and state/canton/etc., to detect the
dates of country-/statewide holidays and adjust the stop times on these dates.

Also, using the command line interface, the user is able to define dates, at which
service differs from the usual schedule, which applies to all columns with a
specific annotation (e.g. `s` or `V` in the figure below).

![Figure showing route annotations][annotations]

## 2.3. Finding stop locations

The final step consists of getting publicly available location data and using
this data along with the information about the routes we have from the pdf,
most notably the duration it takes to get from one stop to the next, as well
as which stops are part of a route.
This is also the reason, why we create the GTFS files first,
because now, we can simply retrieve the information from our GTFS datastructures.

### Fetching the data

As stated above, we use
[QLever](https://github.com/ad-freiburg/qlever) to query
[OpenStreetMap](https://www.openstreetmap.org/).\
When first running pdf2gtfs or when the local cache is not used, the OSM data
is fetched using QLever.
An excerpt of the raw data we get when running our
[query](https://qlever.cs.uni-freiburg.de/osm-germany/?query=PREFIX+osmrel%3A+%3Chttps%3A%2F%2Fwww.openstreetmap.org%2Frelation%2F%3E+%0APREFIX+geo%3A+%3Chttp%3A%2F%2Fwww.opengis.net%2Font%2Fgeosparql%23%3E+%0APREFIX+geof%3A+%3Chttp%3A%2F%2Fwww.opengis.net%2Fdef%2Ffunction%2Fgeosparql%2F%3E+%0APREFIX+osm%3A+%3Chttps%3A%2F%2Fwww.openstreetmap.org%2F%3E+%0APREFIX+rdf%3A+%3Chttp%3A%2F%2Fwww.w3.org%2F1999%2F02%2F22-rdf-syntax-ns%23%3E+%0APREFIX+osmkey%3A+%3Chttps%3A%2F%2Fwww.openstreetmap.org%2Fwiki%2FKey%3A%3E+%0ASELECT+%3Flat+%3Flon+%3Fpublic_transport+%3Frailway+%3Fbus+%3Ftram+%3Ftrain+%3Fsubway+%3Fmonorail+%3Flight_rail+%28GROUP_CONCAT%28%3Fname%3BSEPARATOR%3D%22%7C%22%29+AS+%3Fnames%29+WHERE+%7B+%0A%7B%0AVALUES+%3Ftransport_type+%7B+%22station%22+%22stop_position%22+%22platform%22+%7D%0A%3Fstop+osmkey%3Apublic_transport+%3Ftransport_type+.%0A%3Fstop+osmkey%3Apublic_transport+%3Fpublic_transport+.+%0A%3Fstop+rdf%3Atype+osm%3Anode+.+%0A%3Fstop+geo%3AhasGeometry+%3Flocation+.+%0A%7B+%7B+%7B+%7B+%7B+%3Fstop+osmkey%3Aname+%3Fname+.+%0A%09%09+%7D+UNION+%7B+%3Fstop+osmkey%3Aalt_name+%3Fname+.+%0A%09%09+%7D+%0A%09+%7D+UNION+%7B+%3Fstop+osmkey%3Aref_name+%3Fname+.+%0A%09+%7D+%0A%09+%7D+UNION+%7B+%3Fstop+osmkey%3Ashort_name+%3Fname+.+%0A+%7D+%0A+%7D+UNION+%7B+%3Fstop+osmkey%3Aofficial_name+%3Fname+.%0A+%7D+%0A+%7D+UNION+%7B+%3Fstop+osmkey%3Aloc_name+%3Fname+.+%0A+%7D+%0AOPTIONAL+%7B+%3Fstop+osmkey%3Arailway+%3Frailway+.+%7D+%0AOPTIONAL+%7B+%3Fstop+osmkey%3Abus+%3Fbus+.+%7D+%0AOPTIONAL+%7B+%3Fstop+osmkey%3Atram+%3Ftram+.+%7D+%0AOPTIONAL+%7B+%3Fstop+osmkey%3Atrain+%3Ftrain+.+%7D+%0AOPTIONAL+%7B+%3Fstop+osmkey%3Asubway+%3Fsubway+.+%7D+%0AOPTIONAL+%7B+%3Fstop+osmkey%3Amonorail+%3Fmonorail+.+%7D+%0AOPTIONAL+%7B+%3Fstop+osmkey%3Alight_rail+%3Flight_rail+.+%7D+%0ABIND+%28geof%3Alatitude%28%3Flocation%29+AS+%3Flat%29+%0ABIND+%28geof%3Alongitude%28%3Flocation%29+AS+%3Flon%29+%0A%7D+%7D%0AGROUP+BY+%3Flat+%3Flon+%3Fpublic_transport+%3Frailway+%3Fbus+%3Ftram+%3Ftrain+%3Fsubway+%3Fmonorail+%3Flight_rail%0AORDER+BY+DESC%28%3Frailway%29+DESC%28%3Fbus%29+DESC%28%3Ftram%29)
, can be seen below (it is only sorted to show some of the OSM-key values).

![QLever query result][qlever_query_result]

### The DataFrame

After executing the query on QLever, we have a DataFrame, with the following columns:

- lat/lon: The latitude and longitude of the node
- names: A "|" separated list of different names,
  in particular `name`, `alt_name` and `ref_name`
- A collection of different OSM-keys (like "railway", "bus", "tram", etc.)

### Normalizing names

Before the data is cached, the names will be normalized.
This normalization step is important, because it improves the results of the
search for locations.\
For example, "Frankfurt am Main Hauptbahnhof" and "Frankfurt a. M. hbf" describe
the same location, using different words.
Through normalization, both names will be turned into "frankfurt am main hauptbahnhof",
which makes the equality obvious and "understandable" for the program.

###### Fixing abbreviations

Because some stop names can be quite long, they are often abbreviated in the PDF
in some way.
Using the user-configured abbreviations dictionary, all abbreviations are
expanded to their full form (e.g. "Frankfurt Hbf" is turned into
"Frankfurt Hauptbahnhof").\
There are some caveats, to when abbreviations are extended.
See the [default configuration]() for more info.

###### Removal of parentheses and symbols

Any character of the stop names, that is not a "normal" (i.e. latin) letter,
number or the pipe symbol ("|") is removed.
Any parentheses, as well as their contents are removed from each name, as well.

###### Casefolding and lowering

Some letters can be written in different ways,
e.g. "Laßbergstraße" and "Lassbergstrasse", even though they describe the same stop.
The names are [casefolded](https://docs.python.org/3/library/stdtypes.html#str.casefold),
resulting in the latter version of the example.\
All names are also converted to lower case, for the exact same reason.

###### Cache

After the normalization, the DataFrame will be saved to the cache directory
(`~/.cache/pdf2gtfs/` for Linux, `%LOCALAPPDATA%/pdf2gtfs/` for Windows).\
The cache not only includes the data, but the date of
fetching, the query and the used abbreviations dictionary, as well.
This is to ensure, that the data is fetched again, if either the query or
the abbreviations dictionary are changed. The data is fetched again as well,
if the cache is too old (default: 7 days).

### Preparing the DataFrame

At this point, the DataFrame looks like this:

![Cleaned DataFrame][clean_osm_dataframe]

What we need however, is a DataFrame, that makes it easy to decide which of
two locations is better for a specific stop.\
For this, we create a new DataFrame with these columns:

* `lat/lon`: The latitude/longitude of the location
* `names`: The normalized names
* `stop_id`: identifier for the stop, which is contained in the names column.
  This is the same identifier as the one used in `stops.txt`.
* `node_cost`: the raw costs of the node based only on the selected route type
  (See [#Calculating the node cost](#calculating-the-node-cost)).
* `name_cost`: the lowest edit distance between any of the names and the actual
  stop name (See [#Calculating the name cost](#calculating-the-name-cost)).

We do so, in multiple steps:

1. Filter the current DataFrame `df1`, such that it only contains
   locations with names, which contain *any* of the stop names.
2. Create a new DataFrame `df2` with the above columns.
3. For every stop, filter `df1` by the stops normalized name. Add the result to `df2`
   and calculate the name_cost. Add the stop's stop_id as well.
4. Calculate the node cost for every location in `df2`

The reason we first filter by all stop names, is to make the subsequent filtering
faster.\
Also note that, because we do check for full equality, but instead
only if the stops name is *contained* in the locations name(s), some
locations may occur multiple times in the DataFrame.
For example, if there is a location with the name "Freiburg Bahnhof" and we
have two stops `S1` and `S2` with names "Bahnhof" and "Freiburg Bahnhof",
respectively, he DataFrame will then contain the location twice.
Once with the stop_id and name_cost for `S1` and once with the stop_id and
name_cost for `S2`.

[//]: # (
Now, `df2` looks like this:
![split_dataframe][split_dataframe]
)

###### Calculating the node cost

As stated above, each node on OpenStreetMap, contains one or more
key-value pairs, which specify its function or give some additional information.
The cost of a specific node is calculated for the specified `routetype` using a simple map.
For example, the `railway`-key can be set to, among others, `station`, `halt`
and `tram_stop`. The `tram`-key can be set to `yes` and `no`.\
If the routetype is "Tram", the cost of a node with
`railway=halt` will be higher than the cost of a node with the `railway=tram_stop`
or `tram=yes`. A node without any matching key-value pair will have even
higher cost, while a node with `tram=no` will not be considered at all.

###### Calculating the name cost

To get the name cost, we simply calculate the edit-distance between
the (normalized) stop name and each name of the location's names.
The name cost is the lowest of these edit distances.

### Finding the best locations

The detection of the best combination of locations can be specified as a
shortest path problem in a directed, weighted graph.
For this, every possible location is a node and each node `N1` is connected with
a directed edge, with weight `T`, to another node `N2`, iff `N1` is a node
for the preceeding stop of `N2`. `T` is defined as the sum of the
node-, name- and travel cost of the target node `N2`.
We use Dijkstra's algorithm to find the shortest path.

We start, by creating a Node object for each location and assigning each Node
for the first Stop a travel cost of 0. All nodes are stored in a min heap,
to easily get the Node with the lowest cost.\
Then we simply apply Dijkstra's algorithm:

1. Select the Node with the smallest cost, that is not a visited Node
2. For every neighbor `N` of the current Node `C` set the parent of `N` to `C` if
    * `N` has no parent,
    * `C` is not a MissingNode and `N`'s current parent is a MissingNode
    * or the cost of `N` + the travel cost of `C` to `N` are smaller than the
      cost of `N` + the travel cost of `N`'s current parent to `N`
3. Add `C` to the visited nodes

If `C` is a Node with the last stop as its stop, we are done.

###### Neighbors of a Node

Technically, all nodes of the next stop are the neighbors of a Node `N`.
However, to reduce the number of exact distance calculations (which are slow),
when updating the neighbors of `N`, we first filter the
neighbors by their rough distance. For example, it makes no sense, that a bus
travels 100km in 3 minutes. This also prevents, that `N` is set to be
another node's parent if it is too far away, even if the node's current parent
is a MissingNode.\
Therefore, given the time it takes to travel from
one stop to the next and the user-specified average speed of the vehicle,
we only pay attention to those neighbors, that are closer than the
maximum expected distance.\
To put simply, we draw a square of size `s` with `N` at its center, where `s`
is twice the maximum expected distance and only consider neighbors
within that square to be "true" neighbors.

To do that, we use the following two formulas to calculate the approximate distance
depending on the difference in latitude and longitude:
$$\text{lat distance per degree lat} = | 111.34 * lat_d | $$
$$\text{lon distance per degree lon} = | 111.34 * \cos{(lat_m)} * lon_d | $$
where lat<sub>d</sub> and lon<sub>d</sub> are the difference in latitude/longitude
respectively and lat<sub>m</sub> is the latitude of the midpoint.
The reason we need the cosine of the latitude for the longitude distance, is that
the longitude distance per degree longitude changes, depending on the latitude.\
The above formulas are approximations, but are good enough, to determine if two
locations are somewhere close to each other. Most importantly, they are a lot faster
than calculating the exact distance.

###### Handling missing locations

Because we only filter the locations based on the stop names, it can happen,
that the location of a stop could not be found. In such a case a MissingNode is
used, to still enable the location detection for the other stops. Missing nodes have
a very high node cost, to ensure that existing nodes with high travel cost are
still preferred.

###### Routes

The algortihm described above will be used on every distinct
(in terms of stops served) route in the PDF.\
For example, given the timetable below, there are routes that start either in
"Bad Herrenalb" (`R1`), "Ittersbach Rathaus" (`R2`) or "Ettlingen Albgaubad" (`R3`).
Because the routes starting in "Bad Herrenalb" never serve some of the stops
of the timetable, the location of these stops will not be calculated using those
routes.

![routes_example][routes_example]

Once the locations for all routes have been detected, we select the location
for a single stop, based on all routes serving that stop. E.g. if the location
we found for the stop "Ettlingen Stadt" is the same for the routes `R1` and `R2`,
then it will be the one used in the GTFS feed, even if `R3`
found a different location.

###### Displaying the locations

Mainly for debugging purposes or for a quick visual verification,
the locations of the Nodes can be displayed using
[folium](https://python-visualization.github.io/folium/).

![routedisplay][routedisplay]

### Writing the GTFS feed to disk

Once the shortest path has been found, we add the locations to the respective
stops in the GTFSStops.
For this, the location for any MissingNode is interpolated using the
surrounding existing nodes and a note will be added to the stop's description,
in order to make clear that the location is only approximate.\
Afterwards all GTFS files are zipped into a GTFS feed, which is written to disk,
and the program closes.

# 3. Configuration

Most of the program is configurable by creating configuration files or,
for frequently used options, using the available command line arguments.
This includes (a full list/description can be found in the default configuration):

- `max_row_distance`: The maximum distance in pts, between two rows,
  for them to be considered part of the same table.
- `time_format`: The format used by the given times. Can be any string supported by
  [strftime](https://docs.python.org/3/library/datetime.html#datetime.datetime.strftime).
- `average_speed`: The average speed of the transportation vehicle
- `arrival_identifier/departure_identifier`: Text used in the column following the
  stops, to identify if the vehicle arrives or departs at the specified times.

If a timetable was not read properly, or the detected locations contain many
missing nodes, adjusting these options may help.

# 4. Evaluation

Some rough evaluation of the GTFS feed has been done, to ensure the program
works properly. The full evaluation of pdf2gtfs will be the topic of my
Bachelor's thesis.

###### GTFS feed

Validation of the GTFS feed has been done using
[gtfs-validator](https://github.com/MobilityData/gtfs-validator), which
showed neither warnings, nor errors. This tool checks, if all required
files and values exist and have the correct format/type respectively,
and that all values are valid. It also checks if two stops are too far away,
given their locations and the time it takes to get from one to the other.

###### Location matching

Some locations were not found by pdf2gtfs, even if they actually exist on OSM.
This is due both to the manner the dataset is filtered (i.e. using the stop name),
and the fact that some of the transit agency names differ from the names used in OSM.\
At the same time, the average distance between the locations, that *were* found,
and the actual stop's location is roughly within 100m.
To ensure this is not simply due to a selection bias, other PDF files
from different (previously unseen) agencies were used, without further
changing the code (only changing configuration), which lead to similar results.

Also, sometimes the name of a stop is a single, really broad term, like
"Bahnhof" for example. This results in a huge performance drop in the location
detection, because of the number of locations with "Bahnhof" in their name.

###### Transposed tables

Some input PDFs could not be read properly, for example the one below.
This may occur, when the PDF uses a format for the timetables, which is not
recognized, or is the case here.\
This may also happen, if the chosen options do not adhere to the (observed)
requirements of the timetable format.
For example, setting `min_row_count = 10`, if the timetables only contain 8 rows.

![transposed_table][transposed_table]

###### OpenStreetMap data density

<figure id="figure_osm_heatmap">
    <img src="/img/project-transform-timetables-into-gtfs/osm_comparison.png"
     alt="Heatmap of the whole world showing possible stop locations" style="width:100%">
    <figcaption style="font-size: 13px">
    Heatmap of OSM nodes, that have the key public_transport set to one of
    "stop_position", "platform" or "station"<sup>[1]</sup>
    </figcaption>
</figure>

During development, focus laid on german transit agencies, meaning the location
detection (obviously) used the OSM data for Germany.
However, as seen in the heatmap above, the density of available, useful data
in Germany (and Europe in general) is a lot higher than in most other countries.\
In other words, depending on country and probably population density as well,
the results may be a lot worse than displayed here.

# 5. Conclusion and future plans

The program fulfills the project requirements.\
However, more work can be done,
in particular to widen the support for different timetable formats and to
improve the location detection if the names in OpenStreetMap and the input PDF
differ.

## Future plans

In the following are some features, which may be implemented in the future,
along with some possible implementations.

### Multi-line stopnames

Currently the tables are read line for line, and every line of a single table
has unique y-coordinates.
To properly detect and support stops spanning multiple lines, one possible
implementation would be to simply merge stop columns, such that each field
in the column is merged with the next one, iff the field's row does not
contain any data fields.\
However this approach does come at the cost of only supporting those
multi-line-stops, where the first row of each stop contains data fields.
If the data is centered vertically instead, this implementation would result
in incorrect stop names.

### Supporting differently styled timetables

Timetables using columns to display the stops, i.e. the stops are on the
top of the table and the stop times are written left to right, are unsupported.
This style is widely used in in North America. One possible approach to support
this style would be to simply transpose the PDFTable.

### Rotated stopnames

Another problem that often occurs with transposed timetables, is the existence
of rotated characters. While in the normal style, where each line is a stop and
each column a route, the number of stops can be considerably high, for
the transposed style the number of stops is limited by the length of the stop names
and width of the page.\
To mitigate this and allow for longer routes, the characters/stops are typically
written at an angle (usually between 30 and 90 degrees).
To enable extraction of tables with rotated stopnames, we need to first detect their
position. Afterwards, given the rotated characters and the calculated angle,
we can reconstruct the actual stop name.

### Font-based context

Currently all characters in the PDF are treated the same way, regardless of their
font-properties (e.g. size, bold, italic, ...). To support timetables such as these,
more work needs to be done in regards to properly detecting the properties, and
giving the user some (simple) way of applying meaning to each property.

Font properties are used for example in some timetables in the USA,
which use bold stop times to indicate PM times.
However, we first need to check if there is actually a wide range of
varying usage of these properties. Otherwise, adding more options to the config
(e.g. `bold_times_indicate_pm`/etc.), each handling a single context usage,
would probably be the simplest solution to support this.

### Increase/improve usage of QLever

The query to QLever can probably be improved performance-wise, or to get
more key-value pairs in order to improve the node cost function.
For example, OSM has multiple GTFS-related
keys, which would not only improve the stop-to-location-matching,
but could provide additional information like the official stop_id as well.

Alternatively we could also use QLever to perform the first, rough filter-step
as well, leveraging its speed.
However, considering the cache will not be usable, because the first filter step
depends on the given stops, more testing is required to determine if,
and how much the performance is expected to increase, if this was implemented.

### Allow other services than QLever + OSM

As mentioned before, one caveat is that OSM contains exceptional amounts of
information, when it comes to Germany or Europe in general. In other countries,
the number of different stop locations may be a significantly lower.
In such cases, usage of other services which provide an interface to
retrieve the stop locations, as well as the necessary metadata, could prove
essential to further improving the performance of the location detection in
other parts of the world.

### Allow multiple input files

In case the user has a lot of PDFs, for example for every bus route of a
single agency, it makes sense to output all information in a single GTFS feed.
Currently reading multiple PDF files is not possible.
Before implementing, further testing needs to be done, to ensure that the program
state after processing one PDF does not alter the output of processing another.

### Performance improvements

Location detection is the, computationally, most expensive part.
Once we have created the GTFS datastructures, we could parallelize the location
detection. This would involve creating multiple worker threads, which find
the locations of the stops for all routes.

[//]: # (images)

[vag_linie_1]: /img/project-transform-timetables-into-gtfs/vag_1_table_1.png

[osm_comparison]: /img/project-transform-timetables-into-gtfs/osm_comparison.png

[datastructure_layout]: /img/project-transform-timetables-into-gtfs/layout_datastructures.png

[ala_linie_1]: /img/project-transform-timetables-into-gtfs/ala_linie_1.png

[connection_example]: /img/project-transform-timetables-into-gtfs/connection.png

[repeat_column]: /img/project-transform-timetables-into-gtfs/repeat_column.png

[annotations]: /img/project-transform-timetables-into-gtfs/annotations.png

[field_col_row_visual]: /img/project-transform-timetables-into-gtfs/field_col_row_visual.png

[qlever_query_result]: /img/project-transform-timetables-into-gtfs/qlever_query_result.png

[clean_osm_dataframe]: /img/project-transform-timetables-into-gtfs/clean_osm_dataframe.png

[transposed_table]: /img/project-transform-timetables-into-gtfs/transposed_table.png

[routes_example]: /img/project-transform-timetables-into-gtfs/routes_example.png

[routedisplay]: /img/project-transform-timetables-into-gtfs/routedisplay.png

[//]: # (links)

[la_params]: https://wiki.openstreetmap.org/wiki/Key:ref_namettps://pdfminersix.readthedocs.io/en/latest/reference/composable.html#api-laparams

# Sources:

\[1\]: Displayed using QLever's Map View++ on this
[query](https://qlever.cs.uni-freiburg.de/osm-planet/?query=PREFIX+geo%3A+%3Chttp%3A%2F%2Fwww.opengis.net%2Font%2Fgeosparql%23%3E%0APREFIX+osm%3A+%3Chttps%3A%2F%2Fwww.openstreetmap.org%2F%3E%0APREFIX+rdf%3A+%3Chttp%3A%2F%2Fwww.w3.org%2F1999%2F02%2F22-rdf-syntax-ns%23%3E%0APREFIX+osmkey%3A+%3Chttps%3A%2F%2Fwww.openstreetmap.org%2Fwiki%2FKey%3A%3E%0ASELECT+%3Fstop+%3Fstop_loc+WHERE+%7B%0A++%7B+%3Fstop+osmkey%3Apublic_transport+%22stop_position%22+.+%7D+UNION+%7B+%7B+%3Fstop+osmkey%3Apublic_transport+%22platform%22+.+%7D+UNION+%7B+%3Fstop+osmkey%3Apublic_transport+%22station%22+.+%7D%0A+%7D%0A++%3Fstop+rdf%3Atype+osm%3Anode+.%0A++%3Fstop+geo%3AhasGeometry+%3Fstop_loc%0A%7D)

\[2\]: https://wiki.openstreetmap.org/wiki/Key:ref_name
