import redis
from ._sensors_schemas import *
from contextlib import suppress
from datetime import datetime
from redis.commands.json import JSON as REJSON_Client

# Has to be in order due to shape of data. [temp, humid, airpressure].
# Only if device sends data with out any key/label
UNLABELED_DATA = ("temperature", "humidity", "airpressure")


def transform_to_model(data: RawListData | MeasurementData) -> MeasurementData | None:
    # Check if data is empty. Uses __bool__ in Models.
    if not data:
        return None

    # Valid shape already
    if isinstance(data, MeasurementData):
        return data

    return MeasurementData.parse_obj(dict(zip(UNLABELED_DATA, data)))


def test_value(key: str, value: int | float) -> bool:
    min_range = max_range = None
    match key.lower():
        case "temperature":
            min_range = -50
            max_range = 60
        case "humidity":
            min_range = 0
            max_range = 100
        case "airpressure":
            min_range = 900
            max_range = 1150

    if not (min_range is None or max_range is None):
        return min_range <= value <= max_range
    return False


def validate_time(r_conn: REJSON_Client, location: str, device: str, new_time: datetime) -> bool:
    # Redis-path doesn't exist | Value is None when using .fromisoformat(...)
    with suppress(redis.exceptions.ResponseError, TypeError):
        old_time = datetime.fromisoformat(r_conn.get("sensors", f".{location}.{device}.time"))
        return old_time < new_time
    return True


def set_json(r_conn: REJSON_Client, path: str, elem, rootkey="sensors") -> bool:
    try:
        return r_conn.set(rootkey, path, elem)
    except redis.exceptions.ResponseError:
        if r_conn.get(rootkey) is None:
            r_conn.set(rootkey, ".", {})

        rebuild_path = ""
        for p in path.split(".")[1:]:
            tmp = rebuild_path + "." + p
            if r_conn.get(rootkey, "." if not rebuild_path else rebuild_path).get(p) is None:
                r_conn.set(rootkey, tmp, {})
            rebuild_path = tmp
        return r_conn.set(rootkey, rebuild_path, elem)
