import json
import redis
from redis.commands.json import JSON as REJSON_Client
from datetime import date
from fastapi import FastAPI



db = SQLAlchemy()
DB_NAME = "main_db.db"
local_addr = (["192", "168"], ["127", "0"])
memcache = PooledClient("memcached:11211", serde=JSerde())


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KET"] = "secret"  # No cookies or anything that tracks users...
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:////db/{DB_NAME}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.json_encoder = CustomJSONEncoder
    db.init_app(app)
    # create_db(app)
    with app.app_context():
        db.session.execute("PRAGMA foreign_keys=on")

    # from .views import views

    # from .auth import auth
    from . import datavisualizer, booking, data, views

    # from .booking import booking
    # from .data import data

    app.register_blueprint(views, url_prefix="/")
    # app.register_blueprint(auth, url_prefix="/")
    app.register_blueprint(booking, url_prefix="/booking")
    app.register_blueprint(datavisualizer, url_prefix="/dataviz")
    app.register_blueprint(data, url_prefix="/data")

    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, "static"),
            "favicon.ico",
            mimetype="image/vnd.microsoft.icon",
        )

    return app


# def create_db(app):
#     if not os.path.isfile(DB_NAME):
#         from .models import Notes

#         db.create_all(app=app)


class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        try:
            if isinstance(obj, date):
                return obj.isoformat("T")
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return JSONEncoder.default(self, obj)
