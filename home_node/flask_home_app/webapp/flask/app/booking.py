from flask import Blueprint, render_template, request, jsonify
from . import local_addr, memcache
import modules.sab as sab

# from flask_jwt_extended import create_access_token

booking = Blueprint("booking", __name__)


@booking.context_processor
def inject_enumerate():
    return dict(enumerate=enumerate)


@booking.route("")
def home():
    local = request.headers.get("X-Forwarded-For").split(",")[0].split(".")[:2] in local_addr
    if local:
        if data := sab.get_data():
            printables = sab.get_printables_dict(data)
            memcache.set("booking_data", data, expire=600)
            return render_template(
                "booking.html",
                title="Booking",
                data=printables,
                keys=sorted(printables),
                local=local,
            )
        else:
            return render_template("booking.html", title="Booking failed", failed=True)
    return render_template("booking.html", title="Booking not local", local=local)


@booking.route("/api", methods=["GET", "POST"])
def api():
    if request.headers.get("X-Forwarded-For").split(",")[0].split(".")[:2] in local_addr:
        try:
            if request.method == "GET":
                if data := sab.get_data(True):
                    memcache.set("booking_data", data, expire=600)
                    return jsonify(
                        sab.is_bookable(
                            data, request.args.get("location"), request.args.get("timeslot")
                        )
                    )
            else:
                username, password = request.form.get("user"), request.form.get("pass")
                datajs = memcache.get("booking_data")
                url = (
                    datajs.get(request.form.get("loc_key"))
                    .get(request.form.get("time_key"))
                    .get("url")
                )
                if url and username and password:
                    res = sab.post_data(url, username, password)
                    return jsonify({"res": res[0], "msg": res[1]})
        except:
            pass
    return ("", 204)
