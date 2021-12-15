# DO not use, this is from another project and currently just a placeholder.


# Default, remove, upload and restart
default:
	docker stop $$(docker ps -a -q)
	echo -e "\n@chromium-browser --kiosk --incognito http://raspberrypi" >> autostart
	mv -f autostart ~/.config/lxsession/LXDE-pi/autostart
	cd ./docker/ && docker-compose up --build -d

# refreshes webpage. real horrible solution
refresh:
	export DISPLAY=:0; xdotool search --onlyvisible --class Chromium windowfocus key ctrl+r

# Kills all docker containers
kill:
	docker stop $$(docker ps -a -q)
