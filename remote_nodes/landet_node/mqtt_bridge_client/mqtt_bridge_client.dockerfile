FROM python:slim

ENV CONTAINER_HOME=/app

WORKDIR $CONTAINER_HOME
COPY requirements.txt $CONTAINER_HOME

RUN apt-get update && apt-get -y install gcc
#build-essential libssl-dev libffi-dev python3-dev cargo
RUN pip install --no-cache --upgrade pip setuptools
RUN pip install --no-cache-dir -r requirements.txt
