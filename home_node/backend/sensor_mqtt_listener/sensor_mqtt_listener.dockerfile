FROM python:alpine

WORKDIR /usr/src/app
COPY . .

RUN pip install --no-cache --upgrade pip setuptools
RUN pip install --no-cache-dir -r requirements.txt