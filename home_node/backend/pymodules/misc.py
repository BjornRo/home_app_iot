import os
import secrets


def create_or_ignore_secretkeyfile(length_hex: int = 64) -> str:
    filename = "secretkeyfile"
    # Check if secret key exists, else randomly generate one.
    if not os.path.isfile(filename):
        with open(filename, "w") as f:
            f.write(secrets.token_hex(length_hex))
    with open(filename, "r") as f:
        return f.read().strip()
