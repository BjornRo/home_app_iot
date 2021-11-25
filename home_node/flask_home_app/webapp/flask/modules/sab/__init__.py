import configparser
from typing import Union
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import configparser
import pathlib

cfg = configparser.ConfigParser()
cfg.read(pathlib.Path(__file__).parent.absolute() / "config.ini")

# Timeout for requests, default 10.
timeout = cfg["SETTINGS"].getint("timeout")
timeform = cfg["SITE_DATA"]["timeform"]

# URL
main_url = cfg["SITE_DATA"]["protocol"] + cfg["SITE_DATA"]["hostname"]
query_url = main_url + cfg["SITE_DATA"]["path"]
query = cfg["SITE_DATA"]["query"]
strip_url = cfg["SITE_DATA"]["strip_url"]
suffix = cfg["SITE_DATA"]["suffix"]

# Misc
days = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
del cfg
del configparser
del pathlib

def get_data(single=False) -> Union[dict, None]:
    time_now = datetime.now()
    year, week, wkday = time_now.isocalendar()
    wkday -= 1
    if listlike := _query(single, year, week, wkday, time_now):
        data = {}
        for i in range(wkday, wkday + 2):
            # Add all slots for the day and next day to the dict
            for j in listlike[i].find_all("li")[1:]:
                # Get booking url. IF time hasn't opened, then the url is none
                url = None
                # If there is no message, then there exist a link. Add the link.
                if not j.find("span", class_="message"):
                    url = (
                        j.find("div", class_="button-holder")
                        .find("a")["href"]
                        .replace(strip_url, "")
                        .replace(suffix, "")
                    )
                # Check status, if neither are true: then booking slot hasn't unlocked yet.
                elif "inactive" in j["class"] or re.search(
                    "drop", j.find("span", class_="message").text, re.I
                ):
                    continue
                # Get "number" of slots, location and time
                loc = re.sub(".*\(|\).*", "", j.find("div", class_="location").text, flags=re.S)
                slots = re.sub("[^>0-9]", "", j.find("div", class_="status").text)
                t_strt_end = [
                    dict(zip(("hour", "minute"), map(int, t)))
                    for t in re.findall("(\d+):(\d+)", j.find("div", class_="time").text)
                ]
                strt_time = datetime(*time_now.timetuple()[:3], **t_strt_end[0])
                if i - wkday:
                    strt_time += timedelta(days=1)

                # Check if all slots are taken and there is 2hours or less, then continue. You can't unbook less than 2hours.
                if slots == "0" and strt_time - time_now <= timedelta(hours=2):
                    continue

                # If current location doesn't exist, and wkday, add an empty dict
                if not data.get(loc):
                    data[loc] = {}

                end_time = strt_time.replace(**t_strt_end[1]).isoformat("T", "minutes")
                strt_time = strt_time.isoformat("T", "minutes")
                data[loc][strt_time] = {"end_time": end_time, "url": url, "slots": slots}
        return data


# Query site
def _query(single, year: int, week: int, wkday: int, time_now: datetime) -> Union[list, None]:
    if (data := _qry(query.format(year, week))) and not single and wkday == 6:
        data2 = _qry(query.format(*(time_now + timedelta(days=1)).isocalendar()[:2]))
        return (data + data2) if data2 else None
    return data


def _qry(query_arg: str) -> Union[list, None]:
    try:
        resp = requests.get(query_url + query_arg, timeout=timeout)
        return BeautifulSoup(resp.content, "html.parser").find_all("li", class_="day")
    except:
        return None


def get_printables_dict(data) -> dict:
    return {
        location: {
            st_time: {
                "print": (
                    f"{days[datetime.fromisoformat(st_time).weekday()]}, "
                    f"{st_time[-5:]}-{st_dict['end_time'][-5:]}"
                ),
                "slots": st_dict["slots"] if st_dict["url"] else "not unlocked",
            }
            for st_time, st_dict in time_dict.items()
        }
        for location, time_dict in data.items()
    }


def is_bookable(data, loc: str, ts: str) -> Union[bool, None]:
    try:
        e = data.get(loc).get(ts)
        return e["url"] is not None and e["slots"] != "0"
    except:
        return None


def get_url(data, loc: str, time: datetime) -> Union[str, None]:
    try:
        return data.get(loc).get(time).get("url")
    except:
        return None


def post_data(booking_url: str, user: str, passw: str) -> tuple:
    if not (isinstance(booking_url, str) and isinstance(user, str) and isinstance(passw, str)):
        return (False, "Error: Invalid booking url, and/or invalid logindata")
    try:
        # Check if response is correct. Http evaluates: 200-400 is true, else is false.
        if not (resp := requests.get(main_url + strip_url + booking_url + suffix, timeout=timeout)):
            return
    except:
        return (False, "Failed to get booking link")

    # Soupify it, to extract data to post from 'form', then find all inputs.
    soup_response = BeautifulSoup(resp.content, "html.parser").find("form")

    # Data to post
    payload = {}
    for i in soup_response.find_all("input"):
        try:
            payload[i["name"]] = i["value"]
        except:
            pass
    payload["Username"] = user
    payload["Password"] = passw

    # Send data
    try:
        if sent := requests.post(main_url + soup_response["action"], data=payload):
            # Check if the post returned error. If no error, then the statement evaluates as None.
            if not (
                error_msg := BeautifulSoup(sent.content, "html.parser").find("p", class_="error")
            ):
                return (True, "Successfully booked {} at {}")
            else:
                error_code = re.sub(" ", "", error_msg.text.strip()).lower()
                if "maxantalbokningar" in error_code:
                    return (True, "Error: Already booked {} at {}")
                elif "felaktigt" in error_code:
                    return (False, "Error: Wrong username or password.")
                else:
                    return (False, "Error: Failed to book.")
    except:
        pass
    return (False, "Error: Failed to send data.")
