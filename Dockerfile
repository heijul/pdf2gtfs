FROM ubuntu:latest
LABEL maintainer="Julius Heinzinger <julius.heinzinger@gmail.com>"

RUN apt-get update -y && \
    apt-get install -y python3 python3-pip ghostscript && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /pdf2gtfs
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
COPY src src
COPY src/config.template.yaml config.template.yaml
RUN useradd -u 1234 -mU john && chown -R john:john .
USER john
CMD cd src && python3 -m unittest discover test/
