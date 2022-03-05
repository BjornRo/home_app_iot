FROM python:slim

ENV CONTAINER_HOME=/app

WORKDIR $CONTAINER_HOME
COPY requirements.txt $CONTAINER_HOME

RUN pip install --no-cache --upgrade pip setuptools
RUN pip install --no-cache-dir -r requirements.txt