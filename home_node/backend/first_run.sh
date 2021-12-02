#!/bin/bash

# Run this script to update ddns, and get cert for ssl
# Then run the deploy script

set -a; source .env; set +a

PI_ADDRESS='rpis'
MPATH='/app'

SLEEP_TIME=30
DDNS_ADDR=${DDNS_ENV}
SERVER=${SERVER_ENV}
EMAIL=${EMAIL_ENV}
PORT=${PORT_ENV}
ipv6="ip=&ipv6="$(ssh ${PI_ADDRESS} "hostname -I | egrep -o '[0-9a-z:]+:[0-9a-z:]+' | head -n 1")

echo "This will delete the entire appdata folder."
echo "Press y to continue..."
read -rsn1 input
echo $input
if [[ $input != [YyNn] ]]; then
    kill -SIGINT $$
fi

# Update ddns
echo "Querying the ddns"
resp=$(curl -s ${DDNS_ADDR}"clear=true")
if [[ $resp != "OK" ]]; then
    echo "Response was not ok, exiting"
    kill -SIGINT $$
fi
sleep 10
resp=$(curl -s ${DDNS_ADDR}${ipv6})
echo ${resp}

if [[ $resp != "OK" ]]; then
    echo "Response was not ok, exiting"
    kill -SIGINT $$
fi

echo "Sleeping for 30sec to let the domain have time to update."
sleep $SLEEP_TIME

# Upload all files
#Delete and create folders
rsync -avz \
--rsync-path="rm -rf ~${MPATH} \
&& mkdir -p ~${MPATH}/appdata/certbot/letsencrypt \
&& mkdir -p ~${MPATH}/appdata/certbot/www \
&& mkdir -p ~${MPATH}/appdata/db \
&& rsync" \
--include=www/build/ \
--exclude=www/* \
./ ${PI_ADDRESS}:~${MPATH}

# SSH to initialize the keys
ssh ${PI_ADDRESS} "
docker run --rm -i -p 80:80 \
-v ~/app/appdata/certbot/letsencrypt:/etc/letsencrypt \
-v ~/app/appdata/certbot/www:/var/www/certbot \
certbot/certbot:arm32v6-latest certonly \
-d ${SERVER} --verbose --keep-until-expiring \
--agree-tos --key-type ecdsa --register-unsafely-without-email \
--preferred-challenges=http \
--webroot --webroot-path=/var/www/certbot
"