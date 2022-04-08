import asyncio
import logging
import socket
import ssl
import ujson as json
import zlib
from abc import ABC
from contextlib import suppress
from typing import Any


# TODO check if daemon is the correct name for task running in the background.
# "Daemon" will wait on socket and push data into a queue. Recv will then be a non blocking method.
class AsyncAuthSockClient:
    def __init__(
        self,
        ip: str,
        port: int,
        credentials: bytes,
        auto_reconnect=True,
        daemon=False,
        daemon_blocking_read=False,
        daemon_msg_buffer_size=100,
        header_len=2,
        max_msg_size=2024,
    ) -> None:
        self.ip = ip
        self.port = port
        self.usrname = credentials.split(b"\n")[0]
        self.login_credentials = credentials  # b"user\npass
        self.header_len = header_len
        self.max_msg_size = max_msg_size
        self.daemon = daemon
        if daemon:
            self._buffer: asyncio.Queue[str | dict | None] = asyncio.Queue(daemon_msg_buffer_size)
        self.daemon_blocking_read = daemon_blocking_read
        self.auto_reconnect = auto_reconnect
        self.log_ip = f"{ip}:{port}"
        self.log_full = f"{self.usrname} | {ip}"
        # If reconnection and state change Connected -> Disconnected. Then you can use this flag for whatever in the app.
        self.reconnected = False
        self.conn_state: AASCStateABC = AASCStateDisconnected(self)
        # self.ssl = ssl.SSLContext(ssl.PROTOCOL_TLS)
        self.ssl = ssl.create_default_context()

    async def send(self, payload: Any) -> bool:
        return await self.conn_state.send(payload)

    async def recv(self) -> str | dict | None:
        if self.daemon:
            if self.daemon_blocking_read:
                return await self._buffer.get()
            try:
                return self._buffer.get_nowait()
            except asyncio.QueueEmpty:
                return None
        else:
            return await self.conn_state.recv()

    async def connect(self) -> bool:
        return await self.conn_state.connect()

    async def close(self):
        await self.conn_state.close()
        with suppress(Exception):
            # If anything is listening, notify to stop.
            if self.daemon and self.daemon_blocking_read:
                self._buffer.put_nowait(None)

    def _goto_next_state(self, state):
        self.conn_state: AASCStateABC = state
        logging.debug("Current state: " + str(self.conn_state))

    async def __aenter__(self):
        asyncio.create_task(self.connect())
        return self

    async def __aexit__(self, type, value, traceback):
        await self.close()


# loop(disconnected, connecting, connected) --states
class AASCStateABC(ABC):
    def __init__(self, client_handler: AsyncAuthSockClient):
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.client_handler = client_handler
        self.reader = None
        self.writer = None

        self.log_ip = f"{self.client_handler.ip}:{self.client_handler.port}"
        self.log_full = f"{self.log_ip} | Usr: {self.client_handler.usrname}"

    async def send(self, payload: Any) -> bool:
        if self.writer is None:
            raise RuntimeError("Client isn't connected.")

        if isinstance(payload, bytes):
            payload = payload.decode()
        comp_data = zlib.compress(json.dumps(payload).encode())

        self.writer.write(len(comp_data).to_bytes(self.client_handler.header_len, "big") + comp_data)
        await self.writer.drain()
        return True

    async def recv(self) -> str | dict | None:
        if self.reader is None:
            raise RuntimeError("Client isn't connected.")

        # Will throw asyncio.exceptions.IncompleteReadError if disconnect.
        header_bytes = await self.reader.readexactly(1)
        if _rest := self.client_handler.header_len - 1:
            header_bytes += await asyncio.wait_for(self.reader.readexactly(_rest), timeout=2)

        # header_byte_len, to get content length.
        header_len = int.from_bytes(header_bytes, "big")
        if header_len <= 0:
            raise ValueError("Srv sent invalid header: " + header_bytes.decode())
        elif header_len > self.client_handler.max_msg_size:
            raise ValueError(f"Srv send too big msg: {header_len}, max: {self.client_handler.max_msg_size}")

        payload = await asyncio.wait_for(self.reader.readexactly(header_len), timeout=2)

        with suppress(zlib.error):
            payload = zlib.decompress(payload)
        return json.loads(payload)

    async def connect(self) -> bool:
        return False

    def is_connected(self) -> bool:
        return False

    async def close(self) -> bool:
        return True


class AASCStateDisconnected(AASCStateABC):
    def __init__(self, client_handler: AsyncAuthSockClient):
        super().__init__(client_handler)

    async def recv(self):
        return None

    async def send(self, _p):
        return False

    async def connect(self):
        next_state = AASCStateConnecting(self.client_handler)
        self.client_handler._goto_next_state(next_state)
        return await next_state.connect()


class AASCStateConnecting(AASCStateABC):
    def __init__(self, client_handler: AsyncAuthSockClient):
        super().__init__(client_handler)
        self._connecting_task = None
        self._close = False

    async def recv(self):
        return None

    async def send(self, _p):
        return False

    async def connect(self):
        # Prevent spamming of connections: Already connecting, or closing.
        if self._connecting_task is not None or self._close:
            return True
        self._connecting_task = asyncio.current_task()
        logging.info(f"Connecting to: {self.log_full}")
        while not self._close:
            try:
                task = asyncio.open_connection(
                    self.client_handler.ip,
                    self.client_handler.port,
                    ssl_handshake_timeout=2,
                    ssl=self.client_handler.ssl,
                )
                self.reader, self.writer = await asyncio.wait_for(task, timeout=4)
                if self._close:  # Exit try block and close gently.
                    raise SystemExit
                logging.debug("Logging in...")
                if await self._login():
                    logging.info("Login Successful: " + self.log_full)
                    self.client_handler._goto_next_state(
                        AASCStateConnected(self.client_handler, self.reader, self.writer)
                    )
                    return True
                else:
                    logging.warning("Login failed: " + self.log_full)
            except socket.gaierror:
                logging.info("Could not connect: " + self.log_ip)
            except ssl.SSLError:
                logging.info("Closed before SSL cound finish: " + self.log_ip)
            except asyncio.IncompleteReadError:
                logging.info("Found EOF before expected: " + self.log_ip)
            except asyncio.TimeoutError:
                logging.info("Connection timeout: " + self.log_ip)
            except ConnectionRefusedError:
                logging.info("Probably a port error: " + self.log_ip)
            except ConnectionResetError:
                if not self._close:  # Otherwise writing to closed socket.
                    logging.info("Server force drop connection: " + self.log_ip)
            except SystemExit:
                pass
            except Exception as e:
                logging.warning("Some exception occured: " + str(e))

            # Try to reconnect, reset
            with suppress(Exception):
                self.writer.close()  # type:ignore - Can be none.
                await self.writer.wait_closed()  # type:ignore

            self.writer, self.reader = None, None

            # Check if user stopped connection.
            if self._close:
                return True

            # Otherwise reconnect.
            logging.info("Retrying to connect...")
            await asyncio.sleep(4)

    async def close(self):
        if self._close:
            return True

        self._close = True

        # Close the writer and reader.
        with suppress(Exception):
            self.writer.close()  # type:ignore - Can be none.
            await self.writer.wait_closed()  # type:ignore
            await self.reader.read(-1)  # type:ignore

        self.writer, self.reader = None, None

        with suppress(Exception):  # stop sleeping etc..
            self._connecting_task.cancel()  # type:ignore
            await self._connecting_task  # type:ignore

        self.client_handler._goto_next_state(AASCStateDisconnected(self.client_handler))
        return True

    async def _login(self) -> bool:
        if self.writer is not None:
            if await super().send(self.client_handler.login_credentials):
                return await super().recv() == "OK"
        return False


class AASCStateConnected(AASCStateABC):
    def __init__(
        self,
        client_handler: AsyncAuthSockClient,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        super().__init__(client_handler)
        if reader is None or writer is None:
            raise ValueError("Reader or writer can't be None")
        self.reader = reader
        self.writer = writer
        self._closing = False
        # Constant read on recv, and then just pull a message from the queue.
        if client_handler.daemon:
            self._daemon_task = asyncio.create_task(self._daemon())

    async def recv(self) -> str | dict | None:
        if self._closing:
            return None

        try:
            return await super().recv()
        except asyncio.exceptions.IncompleteReadError as e:
            if not self._closing:
                logging.info("Early EOF received: " + str(e))
        except ValueError as e:
            logging.info("Server sent invalid message: " + str(e))
        except asyncio.TimeoutError:
            logging.info("Server never responded with data to read/took to long to send.")
        except asyncio.CancelledError:
            logging.info("User closed connection")
        except Exception as e:
            logging.warning("recv extra exception: " + str(e))

        await self.close()
        return None

    async def send(self, payload: bytes | dict | str | list) -> bool:
        if self._closing:
            return False

        try:
            await super().send(payload)
            return True
        except ConnectionResetError:
            if not self._closing:
                logging.info("Lost connection while sending.")
        except Exception as e:
            logging.warning("send extra exception: " + str(e))

        await self.close()
        return False

    async def connect(self) -> bool:
        return True

    def is_connected(self) -> bool:
        return True

    async def _daemon(self):
        with suppress():
            while True:
                val = await self.recv()
                if val is None:
                    break
                if not self.client_handler._buffer.full():
                    self.client_handler._buffer.put_nowait(val)

    async def _next_state(self):
        next_state = AASCStateDisconnected(self.client_handler)
        self.client_handler._goto_next_state(next_state)
        if self.client_handler.auto_reconnect and not self._closing:
            self.client_handler.reconnected = True
            asyncio.create_task(next_state.connect())

    async def close(self):
        if not self._closing:
            return True

        self._closing = True
        # Close the writer and reader.
        with suppress(AttributeError):
            self.writer.close()  # type:ignore - Can be none.
            await self.writer.wait_closed()  # type:ignore
            await self.reader.read(-1)  # type:ignore

        with suppress(Exception):
            self._daemon_task.cancel()
            await self._daemon_task

        self.writer, self.reader = None, None
        await self._next_state()
