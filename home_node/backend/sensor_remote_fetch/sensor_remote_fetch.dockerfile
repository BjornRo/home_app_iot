FROM python:alpine

WORKDIR /usr/src/app
COPY . .

RUN apk update && apk add --update musl-dev gcc libffi-dev
RUN pip install --no-cache --upgrade pip setuptools
RUN pip install --no-cache-dir -r requirements.txt
