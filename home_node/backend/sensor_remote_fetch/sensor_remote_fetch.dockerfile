FROM python:alpine

ENV CONTAINER_HOME=/app

WORKDIR $CONTAINER_HOME
COPY requirements.txt $CONTAINER_HOME

RUN apk update && apk add --update musl-dev gcc libffi-dev
RUN pip install --no-cache --upgrade pip setuptools
RUN pip install --no-cache-dir -r requirements.txt
