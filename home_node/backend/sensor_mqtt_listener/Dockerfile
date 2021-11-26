FROM python:alpine

WORKDIR /usr/src/app
COPY . .

#RUN apk update
#&& apk add --no-cache gcc musl-dev libffi-dev
RUN pip install --no-cache --upgrade pip setuptools
RUN pip install --no-cache-dir -r requirements.txt