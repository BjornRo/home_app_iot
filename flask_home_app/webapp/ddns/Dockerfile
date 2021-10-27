FROM python:alpine

ENV CONTAINER_HOME=/usr/src/app

ADD . $CONTAINER_HOME
WORKDIR $CONTAINER_HOME

RUN apk update && apk add --no-cache gcc musl-dev linux-headers
RUN pip install --no-cache --upgrade pip setuptools
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "__main__.py"]