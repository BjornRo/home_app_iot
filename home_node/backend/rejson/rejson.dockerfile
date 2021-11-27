FROM arm32v7/redis

ENV CONTAINER_HOME=/lib

ADD . $CONTAINER_HOME
WORKDIR $CONTAINER_HOME

RUN chmod +x librejson.so

# RUN apt update && apt upgrade
# RUN apt install build-essential llvm cmake libclang1 libclang-dev cargo git

# RUN ./setup.sh

#RUN apt remove build-essential llvm cmake libclang1 libclang-dev cargo git