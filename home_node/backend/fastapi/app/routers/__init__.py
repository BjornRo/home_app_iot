from fastapi import APIRouter


# Class to be able to route with typing not complaining.
class MyRouterAPI:
    xs: list[APIRouter] = []

    def __init__(self, prefix="", tags=[""]):
        self.router = APIRouter(prefix=prefix, tags=tags)
        MyRouterAPI.xs.append(self.router)
