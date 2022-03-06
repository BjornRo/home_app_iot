from hashlib import new
import json
import re
import redis
from ast import literal_eval
from datetime import datetime
from redis.commands.json import JSON as REJSON_Client
from contextlib import suppress

# Has to be in order due to shape of data. [temp, humid, airpressure].
# Only if device sends data with out any key/label
UNLABELED_DATA = ("temperature", "humidity", "airpressure")


def _transform_to_dict(data: dict | list | int | float | str | None) -> dict | None:
    # Reshape to list[listlike] to check if it is valid.
    if isinstance(data, dict):
        data = list(data.items())

    # Get values into a listlike form - Test valid payload.
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            try:
                data = literal_eval(data.replace(",", "."))
            except:
                return None

    if isinstance(data, int | float):
        data = [data]

    # Listlike data can't be empty.
    if not isinstance(data, list | tuple) or not data:
        return None

    # If data is in nested lists pairs such as [[temp, 11], [airp, 11]], otherwise handle as shallow
    # Checks if data is valid
    first_elem_listlike = isinstance(data[0], list | tuple)
    result: dict[str, int | float] = {}
    for i, j in enumerate(data):
        # First get initial key-values
        if first_elem_listlike:
            # Checks if the format is ok, [[str, v],...] or [v], where v is a int|float.
            if not (isinstance(j, list | tuple) and len(j) == 2):
                return None
            else:
                k, v = j
        else:
            if i >= len(UNLABELED_DATA):
                return None
            k, v = UNLABELED_DATA[i], j

        # Try to salvage if value is accidentally a string
        if isinstance(v, str):
            try:
                v = literal_eval(v.replace(",", "."))
            except:
                return None

        # Check if value is a number-type, and the key is a valid string.
        if isinstance(v, int | float):
            if first_elem_listlike:
                if isinstance(k, str):
                    k = k.lower()
                    # String has to start with characters.
                    # Only match max one "_" between any two strings.
                    # If the string is ending with max one number,
                    #   zero or one "_" is allowed between string and this number.
                    # Reject duplicate keys and bad strings.
                    if (
                        re.match("^[a-z]+(_{0,1}[a-z])*(_{1}[0-9]+|[0-9]*)$", k) is None
                        or result.get(k) is not None
                    ):
                        return None
                    # convert known labels if abbreviated
                    for l in UNLABELED_DATA:
                        if k.startswith(l[:3]):
                            k = l
                            break
                else:
                    return None
            result[k] = v
        else:
            return None
    return result


# Tests and transforms data to suitable range
def _test_adjust_value(location: str, key: str, value: int | float) -> int | float | None:
    try:  # Anything that isn't a number will be rejected by try.
        # Values should be without decimals
        match location.lower():
            case "home":
                value /= 100
            case "remote_sh":
                pass
            case _:
                pass

        min_range = max_range = None
        match key:
            case "temperature":
                min_range = -50
                max_range = 60
            case "humidity":
                min_range = 0
                max_range = 100
            case "airpressure":
                min_range = 900
                max_range = 1150
            case _:
                return value
        if min_range is not None and max_range is not None:
            if min_range <= value <= max_range:
                return value
    except:
        pass
    return None


def _validate_time(r_conn: REJSON_Client, location: str, device: str, new_time: str | None) -> bool:
    path = f".{location}.{device}.time"
    if new_time is not None:
        with suppress(ValueError):
            # Test if timeformat is valid
            new_dt = datetime.fromisoformat(new_time)
            try:
                # Test if data exists. If not, set a placeholder as time.
                old_time = datetime.fromisoformat(r_conn.get("sensors", path))
                if old_time < new_dt:
                    return True
            except redis.exceptions.ResponseError:
                _set_json(r_conn, path, datetime.min.isoformat("T"))
                return True
    return False


def _set_json(r_conn: REJSON_Client, path: str, elem, rootkey="sensors"):
    if r_conn.get(rootkey) is None:
        r_conn.set(rootkey, ".", {})

    rebuild_path = ""
    is_root = True
    for p in path.split(".")[1:]:
        tmp = rebuild_path + "." + p
        if r_conn.get(rootkey, "." if is_root else rebuild_path).get(p) is None:
            r_conn.set(rootkey, tmp, {})
        is_root = False
        rebuild_path = tmp
    r_conn.set(rootkey, rebuild_path, elem)


# for i in SUB_TOPICS:
#     _set_json(r_conn, ".home." + i.split("/")[0], {})
# _set_json(r_conn, ".home.balcony.relay", {})
