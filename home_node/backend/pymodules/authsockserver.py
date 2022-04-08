import logging
import ssl
import socket
import queue
import ujson
import zlib
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from requests import Session
from threading import Lock
from typing import Callable

# TODO instead of blocking ip in app-layer, maybe add ip firewall.

# TODO maybe? change validation to an auth-function, to execute instead of hardcoded


class AuthSocketServer(threading.Thread):
    """Opens a server that requires auth from any hardcoded source (maybe auth function later...).
    Requires SSL(Letsencrypt) certs to hide username and password.

    Auth bytestring is = b"username" + "\n" + b"password"

    Server responds b"OK" if valid password, else b"KO".
    If valid, then infinite loop on packet_handler(..) until packet_handler returns False.
    Which then adds the served socket to a queue to be disconnected and discarded.

    packet_handler is the procedure to do. Use AuthClientHandler to send and recieve messages
    from the client.

    Args:
        port: Port for socket to listen on
        hostname: Address which the server runs on. Not used.
        sslpath: The path to your fullchain.pem and privkey.pem
        package_handler(AuthSockClientHandler): The wrapped function to only care about what the procedures are
            when a package is sent or received.
        header_len: How many bytes to initially read to decode message length. Default: 2
        thread_workers: Number of workers for threadpoolexecutor. Default: 8
        max_connections: Max numbers of simultaneously connected entities. Default: 10
        sock_bufsize: Not correctly implemented socket buffer size.
        max_receive_len: Max length of payload to receive.
        kwargs: **kwargs

        Returns:
            self
    """

    def __init__(
        self,
        port: int,
        hostname: str,
        sslpath: str,
        package_handler: Callable,
        on_connect: Callable = lambda *args, **kwargs: None,
        validate_user: Callable = lambda *args, **kwargs: True,
        blocklist_checker: Callable = lambda *args, **kwargs: False,  # is banned.
        on_block_ip: Callable = lambda *args, **kwargs: None,
        header_len=2,
        daemon=True,
        thread_workers=8,
        max_connections=10,
        max_receive_len=2048,
        **kwargs,
    ):
        threading.Thread.__init__(self)
        if header_len <= 0:
            raise ValueError("Header len has to be a positive int")
        if port <= 0 or port in (443, 80, 22, 25):
            raise ValueError("Invalid port entered " + str(port))
        if max_receive_len <= 0:
            raise ValueError("Max receive length has to be positive int")
        self.daemon = daemon
        self.port = port
        self.hostname = hostname
        self._executor = ThreadPoolExecutor(max_workers=thread_workers)
        self._sslkeys = (sslpath + "fullchain.pem", sslpath + "privkey.pem")
        self._header_len = header_len
        self._max_receive_len = max_receive_len
        self._package_handler = package_handler
        self._on_connect = on_connect
        self._current_connections = 0
        self._blocklist_checker: Callable = blocklist_checker
        self._on_block_ip: Callable = on_block_ip
        self._validate_user: Callable = validate_user
        self._max_connections = max_connections
        self._kwargs = kwargs
        self._context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self._context.load_cert_chain(*self._sslkeys)
        self._authed_client_handlers: dict[str, AuthSockClientHandler] = {}
        self._disconnect_queue: queue.Queue[AuthSockClientHandler | None] = queue.Queue()
        self._disconnect_queue_watcher = None
        self._srvsock = None
        self._closing = False
        self._start_close_lock = Lock()

    def run(self):
        self._start_close_lock.acquire()
        try:
            srv = socket.create_server(("", self.port), family=socket.AF_INET6, dualstack_ipv6=True)
            srv.listen(self._max_connections if self._max_connections < 64 else 64)
            socket.setdefaulttimeout(4)  # For ssl handshake and auth.
            logging.info("Socket server listening on: '{}':{}".format(*srv.getsockname()[:2]))
            self._srvsock = self._context.wrap_socket(srv, server_side=True)

            self._disconnect_queue_watcher = threading.Thread(target=self._connection_thread_watcher)
            self._disconnect_queue_watcher.start()
        except Exception as e:
            logging.warning("Starting server failed: " + str(e))
        self._start_close_lock.release()

        if self._srvsock is None:
            return None

        session = Session()
        while not self._closing:
            try:
                client, addr = self._srvsock.accept()
                ip_addr = addr[0]
                logging.info("Client connected from ip:" + ip_addr)
                if not self._blocklist_checker(session, ip_addr):
                    if self._max_connections > self._current_connections:
                        self._current_connections += 1
                        client_obj = AuthSockClientHandler(self, session, client, **self._kwargs)
                        client_obj.start()
                        logging.info(
                            f"Number of connected users: {self._current_connections}/{self._max_connections}"
                        )
                        continue
                    else:
                        logging.warning("Server has reached max connections: " + str(self._max_connections))
                        with suppress(Exception):
                            client.sendall((2).to_bytes(self._header_len, "big") + b"KO")
                else:
                    # self._on_block_ip(session, ip_addr)
                    logging.warning("Client is banned: " + ip_addr)
                with suppress(Exception):
                    client.close()
            except Exception as e:
                if self._closing:
                    session.close()
                    return None
                logging.info("Client SSL exception: " + str(e))

    def close_server(self):
        with self._start_close_lock:  # If server is starting. Pause this
            pass

        # Server has already been called closing or not started.
        if self._closing or self._srvsock is None:
            return None

        # Stops any pending client connections.
        with self._start_close_lock:
            # Stop sending any new messages
            logging.info("Closing server")
            self._closing = True

            # Close server socket.
            self._srvsock.close()

        # No clients can connect at this point, Server can't send any messages.
        for i in self._authed_client_handlers.values():
            i.close()
        self._disconnect_queue.put(None)
        self._disconnect_queue_watcher.join(timeout=2)  # type:ignore - Can only be none if _srvsock is None.

    def send_to_all(self, payload: str | bytes | dict | list, exclude=[]):
        if self._closing or self._srvsock is None:
            return None

        _exclude: list[AuthSockClientHandler] = exclude
        for client_handler in self._authed_client_handlers.values():
            if client_handler in _exclude or client_handler._is_closing:
                continue
            self._executor.submit(client_handler.send, payload)

    # If any connection fails/stopped, then the client_handler adds itself to be disconnected
    def _connection_thread_watcher(self):
        def _shutdown(client_handler: AuthSockClientHandler):
            logging.debug(
                f"Client shutdown, before cleaup, authed clients: {len(self._authed_client_handlers)} | Threads: {threading.active_count()}"
            )

            if client_handler.name != "":  # Only successful logins, handler get a name, and added to dict.
                with self._start_close_lock:
                    del self._authed_client_handlers[client_handler.name]

            # Close socket
            with suppress(Exception):
                client_handler.client.close()

            self._current_connections -= 1

            logging.debug(f"Thread watcher. Client_handler is thread alive: {client_handler.is_alive()}")
            client_handler.join(timeout=2)
            logging.debug(threading.enumerate())
            logging.debug(
                f"Client shutdown, after cleaup, authed clients: {len(self._authed_client_handlers)} | Threads: {threading.active_count()}"
            )

        logging.debug("Thread watcher started.")
        while True:
            client_handler = self._disconnect_queue.get()
            if client_handler is None:  # Signal the watcher to stop
                return
            self._executor.submit(_shutdown, client_handler)


class AuthSockClientHandler(threading.Thread):
    def __init__(
        self,
        sockserv: AuthSocketServer,
        session: Session,
        client: ssl.SSLSocket,
        daemon=True,
        **kwargs,
    ) -> None:
        super().__init__()
        self.session = session
        self.name = ""
        self.client = client
        self.daemon = daemon
        self.ip = str(client.getpeername()[0])
        self.unused_dict = {}  # For whatever use one want. This will get deleted on disconnect.
        self._passwd = ""  # Do not store valid login passwords. Just for logging invalid ones.
        self._sockserv = sockserv
        self._kwargs = kwargs
        self._is_closing = False

    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return hash(id(self))

    def close(self) -> None:
        if self._is_closing:
            return None

        self._is_closing = True

        self._sockserv._disconnect_queue.put(self)
        return None

    # Any bad received message, then client handler will get closed.
    def run(self) -> None:
        if self._is_closing:
            return None
        try:
            if self._login():
                logging.info("User logged in successfully: " + self.name)
                with self._sockserv._start_close_lock:
                    if self._sockserv._closing:
                        return self.close()
                    elif self.name in self._sockserv._authed_client_handlers:
                        logging.info("User already logged in, disconnecting: " + self.name)
                        self.name = ""
                        return self.close()
                    self._sockserv._authed_client_handlers[self.name] = self
                self.client.settimeout(None)
                self.send(b"OK")
                self._sockserv._on_connect(self)

                while True:
                    packet = self.receive()
                    if packet is None:
                        break
                    self._sockserv._package_handler(self, packet)
            else:
                logging.warning(
                    f"Client failed login, [ip: {self.ip} | usr: {self.name} | pw: {self._passwd}]"
                )
                self.send(b"KO")
                # self._on_block_ip(self.session, self.ip)

        except socket.timeout as e:
            logging.info(f"Socket timeout, ip: {self.ip}, {e}")
        except ConnectionAbortedError as e:
            if not self._is_closing:
                logging.info(f"Socket disconnected, [ip: {self.ip}, location: {self.name}, reason: {e}]")
        except TypeError as e:
            logging.info("Client sent invalid start header: " + str(e))
        except ValueError as e:
            logging.warning(f"Client sent invalid payload: Location: {self.name} | {self.ip} | {e}")
        except Exception as e:  # Just to log if any other important exceptions are raised
            logging.warning("Exception from client handler: " + str(e))
        self.close()
        return None

    def _login(self) -> bool:
        recv = self.receive()
        if recv is not None:
            name, passwd = recv.decode().split("\n")
            if name and passwd:
                self.name = name.lower()
                if self._sockserv._validate_user(self.session, name, passwd):
                    return True
                self._passwd = passwd  # If not valid, store password for logging.
        return False

    def send(self, payload: str | bytes | dict | list):
        if self._is_closing or self._sockserv is None:
            return None

        try:
            if isinstance(payload, str):
                payload = payload.encode()
            elif isinstance(payload, dict | list):
                payload = ujson.dumps(payload).encode()
            comp_payload = zlib.compress(payload, level=9)
            self.client.sendall(len(comp_payload).to_bytes(self._sockserv._header_len, "big") + comp_payload)
        except Exception as e:
            logging.info(f"Failed to send data to [{self.name}]: {e}")
            self.close()
        return None

    def receive(self) -> bytes | None:
        if self._is_closing or self._sockserv is None:
            return None

        # Start timeout from init read. _recvall raises zero-byte error if disconnect.
        init_byte = self._recvall(1)
        self.client.settimeout(2)

        # Get rest of msg size.
        msg_size = int.from_bytes(init_byte + self._recvall(self._sockserv._header_len - 1), "big")
        if not (0 < msg_size <= self._sockserv._max_receive_len):
            raise ValueError(
                f"Expected a message len 0-{self._sockserv._max_receive_len}, received: {msg_size}"
            )

        # Get packet
        recvdata = self._recvall(msg_size)
        self.client.settimeout(None)
        with suppress(zlib.error):
            recvdata = zlib.decompress(recvdata)
        return recvdata

    # Negative receive_len will result in b""
    def _recvall(self, receive_len: int) -> bytes:
        received_chunks = []
        remaining = receive_len
        while remaining > 0:
            received = self.client.recv(remaining)
            if received == b"":
                raise ConnectionAbortedError("recv received zero-byte")

            received_chunks.append(received)
            remaining -= len(received)
        return b"".join(received_chunks)
