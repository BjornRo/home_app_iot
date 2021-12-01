#!/bin/bash


PI_ADDRESS='pi@raspberrypi'
MPATH='/dv_monaden/monaden-signage'

echo "> Compiling REACT locally"

# Install dependencies and build locally
npm install --prefix ./www
npm run --prefix ./www build

echo "> You're about to copy over the contents of monaden-signage to the PIE."

# Upload all files
# Delete and create folders
rsync -avz \
    --rsync-path="rm -rf ~${MPATH} && mkdir -p ~${MPATH}/www/build && rsync" \
    --include=www/build/ \
    --exclude=www/* \
    ./ ${PI_ADDRESS}:~${MPATH}


echo "> You're about to restart the Docker container."

ssh ${PI_ADDRESS} "cd ~${MPATH}; make; make refresh"
