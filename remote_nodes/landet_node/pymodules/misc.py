import argparse
import asyncio

import logging
import functools
import os
import ssl
import tarfile
import ujson
import zlib
from aiofiles import open as async_open
from contextlib import suppress
from io import BytesIO


async def get_filebytes(filename: str, path: str) -> bytes | None:
    filepath = path + filename
    if not os.path.isfile(filepath):
        return None
    async with async_open(filepath, "rb") as f:
        source = BytesIO(await f.read())
    tardb = BytesIO()
    with tarfile.open(fileobj=tardb, mode="w:gz", compresslevel=9) as tar:
        info = tarfile.TarInfo(filename)
        info.size = source.seek(0, 2)
        source.seek(0)
        tar.addfile(info, source)
    return tardb.getvalue()


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


def get_arg_namespace() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--port",
        help="Set port number",
        dest="port",
        action="store",
        required=False,
        type=int,
    )
    parser.add_argument(
        "-d",
        "--debug",
        help="Print lots of debugging statements",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        default=logging.WARNING,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Be verbose",
        action="store_const",
        dest="loglevel",
        const=logging.INFO,
    )
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)
    return args