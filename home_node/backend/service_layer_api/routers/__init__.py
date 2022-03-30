from fastapi import APIRouter


# Class to be able to route with typing not complaining.
class MyRouterAPI:
    xs: list[APIRouter] = []

    def __init__(self, prefix: str | None = None, tags: list[str] | None = None):
        if prefix is None:
            raise ValueError("Prefix must be an unique path/address.")
        if tags is not None and isinstance(tags, list) and not tags:
            raise ValueError("Tags must be a non-empty list of strings")
        self.router = APIRouter(prefix=prefix, tags=tags) # type:ignore
        MyRouterAPI.xs.append(self.router)
