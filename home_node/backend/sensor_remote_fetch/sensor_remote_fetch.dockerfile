FROM python:slim

WORKDIR /usr/src/app
COPY . .

RUN apt-get update && apt-get -y install gcc
#RUN apk update && apk add --no-cache gcc musl-dev libffi-dev
# tzdata musl-dev libffi-dev
#RUN pip install --no-cache --upgrade pip setuptools
RUN pip install --no-cache-dir -r requirements.txt
