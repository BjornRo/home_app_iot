#!/bin/bash

set -a; source .env; set +a

SERVER=${SERVER_ENV}
EMAIL=${EMAIL_ENV}
PORT=${PORT_ENV}

PI_ADDRESS='pi@192.168.1.173'
MPATH='/app'

echo "This will delete the entire appdata folder."
read -p "Press any key to continue..."

# Upload all files
# Delete and create folders
rsync -avz -e "ssh -p ${PORT}" \
--rsync-path="rm -rf ~${MPATH} \
&& mkdir -p ~${MPATH}/appdata/certbot/letsencrypt \
&& mkdir -p ~${MPATH}/appdata/db \
&& rsync" \
--include=www/build/ \
--exclude=www/* \
./ ${PI_ADDRESS}:~${MPATH}

ssh ${PI_ADDRESS} -p ${PORT} "bash -s" << EOF
docker run --rm -i -p 80:80 \
 -v ./appdata/certbot/letsencrypt:/etc/letsencrypt \
 -v ./appdata/certbot/www:/var/www/certbot \
 certbot/certbot:arm32v6-latest certonly \
 -d ${SERVER} --verbose --keep-until-expiring \
 --agree-tos --key-type ecdsa --email ${EMAIL} \
 --preferred-challenges=http \
 --webroot --webroot-path=/var/www/certbot
EOF