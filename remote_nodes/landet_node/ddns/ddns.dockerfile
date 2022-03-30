FROM python:slim

ENV CONTAINER_HOME=/app

WORKDIR $CONTAINER_HOME
COPY . $CONTAINER_HOME

RUN apt-get update && apt-get -y install gcc
#RUN apk update && apk add --no-cache gcc musl-dev linux-headers
RUN pip install --no-cache --upgrade pip setuptools
RUN pip install --no-cache-dir -r requirements.txt