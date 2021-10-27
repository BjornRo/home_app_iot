from datetime import datetime
from flask import Blueprint, render_template, request, jsonify
from . import local_addr, db, memcache
import paho.mqtt.publish as publish
from .models import Notes

views = Blueprint("views", __name__)

@views.route("/")
def home():
    local = request.headers.get("X-Forwarded-For").split(",")[0].split(".")[:2] in local_addr
    return render_template(
        "index.html",
        title="Home",
        data=memcache.get("weather_data_home"),
        local=local,
        rel_status=memcache.get("relay_status"),
    )


@views.route("/notes", methods=["GET", "POST"])
def notes():
    local = request.headers.get("X-Forwarded-For").split(",")[0].split(".")[:2] in local_addr
    return render_template("notes.html", local=local)


@views.route("/notes/api", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def notes_api():
    if request.headers.get("X-Forwarded-For").split(",")[0].split(".")[:2] in local_addr:
        try:
            if request.method == "GET":
                count = int(request.args.get("c"))
                if count == Notes.query.count():
                    return jsonify([])
                return jsonify(
                    [
                        {
                            "time": note.time.strftime("%Y %B %d %H:%M"),
                            "time_key": note.time,
                            "text": note.text,
                        }
                        for note in Notes.query.order_by(Notes.time.asc())
                        .offset(count)
                        .limit(10)
                        .all()
                    ]
                )
            elif request.method == "POST":
                value = request.json.get("newpost")
                if isinstance(value, str) and len(value) >= 1:
                    note = Notes(time=datetime.now(), text=value)
                    db.session.add(note)
                    db.session.commit()
                    return jsonify(
                        {
                            "time": note.time.strftime("%Y %B %d %H:%M"),
                            "time_key": note.time,
                            "text": note.text,
                        }
                    )
            elif request.method == "PATCH":
                time_key, text = request.json.get("time_key"), request.json.get("text")
                if isinstance(text, str) and len(text) >= 1:
                    Notes.query.filter_by(time=datetime.fromisoformat(time_key)).first().text = text
                    db.session.commit()
                    return ("", 204)
            elif request.method == "DELETE":
                time_key = request.json.get("time_key")
                if time_key:
                    db.session.delete(
                        Notes.query.filter_by(time=datetime.fromisoformat(time_key)).first()
                    )
                    db.session.commit()
                    return ("", 204)
        except:
            pass
    return ("", 400)


# Everyone can get this data
@views.route("/home_status")
def home_status():
    return jsonify(
        {
            "weather_data": memcache.get("weather_data_home"),
            "relay_status": memcache.get("relay_status"),
        }
    )


# Pinsetup for arduino. Send 0-3
# By pin index 0-3(2-5): 2: Full light, 3: Low Light, 4: HEATER_PIN, 5: Unused
entities = {"alloff": "ALLOFF", "full_light": 0, "low_light": 1, "heater": 2}
commands = {"off": 0, "on": 1}


@views.route("/post_command", methods=["POST"])
def post_command():
    if request.headers.get("X-Forwarded-For").split(",")[0].split(".")[:2] in local_addr:
        try:
            ent, com = request.form.get("entity").lower(), request.form.get("command").lower()
            if ent in entities and com in commands:
                pub = (
                    entities[ent]
                    if ent == "alloff"
                    else f'({entities[ent]},{commands[com]},{0 if com == "off" else 5 if ent == "full_light" else 420})'
                )
                publish.single("home/balcony/relay/command", pub, hostname="www.home")
                return ("", 204)
        except:
            pass
    return ("", 400)
