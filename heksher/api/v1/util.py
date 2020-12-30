from __future__ import annotations

import orjson
from fastapi import Depends, Request, APIRouter
from pydantic.main import BaseModel

router = APIRouter(prefix='/api/v1')


def orjson_dumps(v, **kwargs):
    return str(orjson.dumps(v, **kwargs), 'utf-8')


class ORJSONModel(BaseModel):
    """
    BaseModel with default orjson loads,dumps
    """

    class Config:
        json_dumps = orjson_dumps
        json_loads = orjson.loads


@Depends
def application(request: Request):
    """
    A helper dependancy to get the app instance
    """
    return request.app
