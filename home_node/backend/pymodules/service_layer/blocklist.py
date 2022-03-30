import os
from datetime import datetime, timedelta
from requests import Session

BAN_TIME = 30  # minutes
ATTEMPT_PENALTY = 5

SERVICE_API = os.environ["SERVICE_API"]
BLOCK_LIST_API = SERVICE_API + "/blocklist"


def get_user_tag(session: Session, username: str, tag: str) -> dict | None:
    resp = session.get(f"{SERVICE_API}/auth/users/{username}/tags/{tag}")
    if resp.status_code < 300:
        return resp.json()
    return None


def get_user_tags(session: Session, username: str) -> list[str]:
    resp = session.get(f"{SERVICE_API}/auth/users/{username}/tags")
    if resp.status_code < 300:
        return resp.json()
    return []


def validate_user(session: Session, username: str, password: str) -> bool:
    json = {"username": username, "password": password}
    return session.post(SERVICE_API + "/auth/verify", json=json).json()


def is_banned(session: Session, ip_addr: str) -> bool:
    return session.get(BLOCK_LIST_API + "/isbanned/" + ip_addr).json()


def block_user(session: Session, ip_addr: str) -> None:
    curr_time = datetime.utcnow()

    resp = session.get(BLOCK_LIST_API + ip_addr)
    # If 400, then user hasn't been previously banned. Add new entry.
    if resp.status_code >= 400:
        session.post(
            BLOCK_LIST_API,
            json={
                "ip": ip_addr,
                "ban_expire": (curr_time + timedelta(minutes=BAN_TIME)).isoformat(),
                "manual_ban": False,
            },
        )
    elif resp.status_code == 200:
        # Increases by 1
        attempts: int = session.patch(BLOCK_LIST_API + ip_addr).json()

        if attempts >= ATTEMPT_PENALTY:
            # Reset to "max" attempts so it is not higher than penalty.
            attempts = ATTEMPT_PENALTY - 1
            multiplier = 5
        elif attempts >= ATTEMPT_PENALTY / 2:
            multiplier = 2
        else:
            multiplier = 1
        dt = curr_time + timedelta(minutes=BAN_TIME * attempts * multiplier)
        session.put(
            BLOCK_LIST_API,
            json={"ip": ip_addr, "ban_expire": dt.isoformat(), "attempt_counter": attempts},
        )
    return None
