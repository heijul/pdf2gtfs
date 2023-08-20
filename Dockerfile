FROM ubuntu:latest
LABEL maintainer="Julius Heinzinger <julius.heinzinger@gmail.com>"

RUN apt-get update -y && \
    apt-get install -y python3 python3-pip ghostscript git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /pdf2gtfs
RUN git clone -b final_0 --recurse-submodules https://github.com/heijul/pdf2gtfs
RUN pip3 install ./pdf2gtfs/custom_conf
RUN pip3 install ./pdf2gtfs

WORKDIR /pdf2gtfs/pdf2gtfs
RUN useradd -u 1234 -mU john && chown -R john:john .
USER john
CMD python3 -m unittest discover test
