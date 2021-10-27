from flask import Blueprint, render_template, request, jsonify, url_for
from . import db

datavisualizer = Blueprint("datavisualizer", __name__)


@datavisualizer.route("/")
def home():
    return render_template("dataviz.html", title="Data visualization")


@datavisualizer.route("/api")
def api():
    data = db.session.execute(
        """SELECT t.time, ktemp, khumid, press, btemp, bhumid, brtemp
FROM Timestamp t
LEFT OUTER JOIN
(SELECT time, temperature AS ktemp
FROM Temperature
WHERE measurer = 'kitchen') a ON t.time = a.time
LEFT OUTER JOIN
(SELECT time, humidity As khumid
FROM Humidity
WHERE measurer = 'kitchen') b ON t.time = b.time
LEFT OUTER JOIN
(SELECT time, airpressure AS press
FROM Airpressure
WHERE measurer = 'kitchen') c ON t.time = c.time
LEFT OUTER JOIN
(SELECT time, temperature AS btemp
FROM Temperature
WHERE measurer = 'balcony') d ON t.time = d.time
LEFT OUTER JOIN
(SELECT time, humidity As bhumid
FROM Humidity
WHERE measurer = 'balcony') e ON t.time = e.time
LEFT OUTER JOIN
(SELECT time, temperature AS brtemp
FROM Temperature
WHERE measurer = 'bikeroom') f ON t.time = f.time"""
    ).fetchall()
    db.session.commit()
    return jsonify(
        (
            (
                "date",
                "kitchen temp",
                "kitchen humid",
                "kitchen pressure",
                "balcony temp",
                "balcony humid",
                "bikeroom temp",
            ),
            data,
        )
    )


# outdoor (temp)
# kitchen (temp humid pressure)

# Grid temp  temp
# ---- humid pressure

"""
WITH kitchendata AS (
        SELECT time, temperature AS ktemp, humidity AS khumid, airpressure AS kpressure
        FROM Temperature
        NATURAL JOIN Humidity
        NATURAL JOIN Airpressure
        WHERE measurer = 'kitchen'),
    balconydata AS (
        SELECT time, temperature AS btemp, humidity AS bhumid
        FROM Temperature
        NATURAL JOIN Humidity
        WHERE measurer = 'balcony'),
    bikeroomdata AS (
        SELECT time, temperature AS brtemp
        FROM Temperature
        WHERE measurer = 'bikeroom')
SELECT kd.time, ktemp, khumid, kpressure, btemp, bhumid, brtemp
    FROM kitchendata kd
    LEFT OUTER JOIN
        balconydata bd
        ON kd.time = bd.time
    LEFT OUTER JOIN
        bikeroomdata brd
        ON kd.time = brd.time"""
