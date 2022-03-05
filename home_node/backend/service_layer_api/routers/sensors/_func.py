from ast import literal_eval
from redis.commands.json import JSON as REJSON_Client

# Has to be in order due to shape of data. [temp, humid, airpressure].
MINOR_KEYS = ("temperature", "humidity", "airpressure")

def _transform_to_dict(data: dict | list | int | float | str) -> dict | None:
    if isinstance(data, dict):
        return data

    # Get values into a listlike form - Test valid payload.
    if isinstance(data, str):
        try:
            data = literal_eval("".join([i for i in data.replace(",", ".") if i.isdigit()]))
        except:
            return None

    if isinstance(data, int | float):
        data = [data]

    for i in data:
        if not isinstance(i, int | float):
            return None

    if len(data) > len(MINOR_KEYS):
        return None

    return {k: v for k, v in zip(MINOR_KEYS, data)}

# Tests and transforms data to suitable range
def _test_value(location: str, key: str, value: int | float) -> int | float | None:
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
        if min_range is not None and max_range is not None:
            if min_range <= value <= max_range:
                return value
    except:
        pass
    return None


def _set_json(r_conn: REJSON_Client, path: str, elem, rootkey="sensors") -> None:
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
