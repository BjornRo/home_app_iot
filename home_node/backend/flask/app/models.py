from . import db

"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config['SQLALCHEMY_ECHO'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
db.session.execute('PRAGMA foreign_keys=on')
"""
# class Measurer(db.Model):
#     key = db.Column(db.String(8), primary_key=True)
#     temp = db.relationship("Temperature", backref="measure", lazy="dynamic")
#     humid = db.relationship("Humidity", backref="measure", lazy="dynamic")
#     press = db.relationship("Airpressure", backref="measure", lazy="dynamic")

# class Timestamp(db.Model):
#     time = db.Column(db.String(16), primary_key=True)
#     temp = db.relationship("Temperature", backref="timestamp", cascade="all, delete", lazy="dynamic")
#     humid = db.relationship("Humidity", backref="timestamp", cascade="all, delete", lazy="dynamic")
#     press = db.relationship("Airpressure", backref="timestamp", cascade="all, delete", lazy="dynamic")

# class Temperature(db.Model):
#     measurer = db.Column(db.String(8), db.ForeignKey('measurer.key'), primary_key=True)
#     time = db.Column(db.String(16), db.ForeignKey('timestamp.time'), primary_key=True)
#     temperature = db.Column(db.Numeric(2), nullable=False)

# class Humidity(db.Model):
#     measurer = db.Column(db.String(8), db.ForeignKey('measurer.key'), primary_key=True)
#     time = db.Column(db.String(16), db.ForeignKey('timestamp.time'), primary_key=True)
#     humidity = db.Column(db.Numeric(2), nullable=False)

# class Airpressure(db.Model):
#     measurer = db.Column(db.String(8), db.ForeignKey('measurer.key'), primary_key=True)
#     time = db.Column(db.String(16), db.ForeignKey('timestamp.time'), primary_key=True)
#     airpressure = db.Column(db.Numeric(2), nullable=False)

class Notes(db.Model):
    time = db.Column(db.DateTime(timezone=True), primary_key=True)
    text = db.Column(db.String(1000), nullable=False)
