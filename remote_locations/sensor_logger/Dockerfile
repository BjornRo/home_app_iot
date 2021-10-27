FROM python:slim

ENV CONTAINER_HOME=/usr/src/app
ENV TZ=Europe/Stockholm

ADD . $CONTAINER_HOME
WORKDIR $CONTAINER_HOME

RUN apt-get update && apt-get -y install gcc
#build-essential libssl-dev libffi-dev python3-dev cargo
RUN pip install --no-cache --upgrade pip setuptools
RUN pip install --no-cache-dir -r requirements.txt
RUN echo "Europe/Stockholm" >  /etc/timezone

#RUN mkdir -p /devices
#RUN ln -s /devices /sys/bus/w1/devices/

CMD ["python3", "__main__.py"]