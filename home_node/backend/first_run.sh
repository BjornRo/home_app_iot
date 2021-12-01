#!/bin/bash

set -o allexport; source .env; set +o allexport

PI_ADDRESS='rpis'
MPATH='/app'
SERVER=${SERVER_ENV}
EMAIL=${EMAIL_ENV}

#sudo apt-get update
#sudo apt-get install certbot python-certbot-nginx

echo "This will delete the entire appdata folder."
read -p "Press any key to continue..."

# Upload all files
# Delete and create folders
rsync -avz \
--rsync-path="rm -rf ~${MPATH} \
&& mkdir -p ~${MPATH}/appdata/certbot/letsencrypt \
&& mkdir -p ~${MPATH}/appdata/db \
&& rsync" \
--include=www/build/ \
--exclude=www/* \
./ ${PI_ADDRESS}:~${MPATH}

ssh rpis << EOF
docker run -it --name certbot \
 -v "./appdata/certbot/letsencrypt:/etc/letsencrypt" \
 -v "./appdata/certbot/www:/var/www/certbot" \
 certbot/certbot:latest certonly \
 -d ${SERVER} --verbose --keep-until-expiring \
 --agree-tos --email ${EMAIL} \
 --preferred-challenges=http \
 --webroot --webroot-path=/var/www/certbot
EOF