from flask import Blueprint, request
from . import memcache
from configparser import ConfigParser
import socket

data = Blueprint("data", __name__)

cfg = ConfigParser()
cfg.read("config.ini")


@data.route("/api", methods=["POST"])
def api():
    return 404
    form = request.form
    if cfg["USER"]["uid"] == form.get("user") and cfg["USER"]["psw"] == form.get("password"):
        data = form.get("data")
        if data is not None:
            memcache.set(form["user"], data)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.connect(("sensor_logger", 9000))
                s.sendall(data.encode())
            return (204, "")
    return 500
