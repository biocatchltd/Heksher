from __future__ import annotations

import orjson
from fastapi import Depends, Request, APIRouter
from pydantic import BaseModel  # pytype: disable=import-error


def orjson_dumps(v, **kwargs):
    return str(orjson.dumps(v, **kwargs), 'utf-8')


class ORJSONModel(BaseModel):  # pytype: disable=base-class-error
    """
    BaseModel with default orjson loads, dumps
    """

    # note that this superclass is ineffectual until https://github.com/tiangolo/fastapi/pull/2347 is merged
    class Config:
        json_dumps = orjson_dumps
        json_loads = orjson.loads


@Depends
def application(request: Request):
    """
    A helper dependancy to get the app instance
    """
    return request.app


router = APIRouter(prefix='/api/v1')
