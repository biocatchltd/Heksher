from __future__ import annotations

from hashlib import md5

import orjson
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import JSONResponse, Response


def orjson_dumps(v, **kwargs):
    return str(orjson.dumps(v, **kwargs), 'utf-8')


class ORJSONModel(BaseModel):
    """
    BaseModel with default orjson loads, dumps
    """

    # note that this superclass is ineffectual until https://github.com/tiangolo/fastapi/pull/2347 is merged
    class Config:
        json_dumps = orjson_dumps
        json_loads = orjson.loads


class PydanticResponse(JSONResponse):
    media_type = "application/json"

    def render(self, content: BaseModel) -> bytes:
        return content.json().encode("utf-8")


@Depends
def application(request: Request):
    """
    A helper dependency to get the app instance
    """
    return request.app


def handle_etag(response: Response, request: Request):
    """
    A utility function to add etag to a response, and to check whether the request has the same etag.
    """
    response_etag = response.headers.get('ETag')
    if response_etag is None:
        hasher = md5()
        hasher.update(response.body)
        response_etag = response.headers['ETag'] = f'"{hasher.hexdigest()}"'
    if_none_match = request.headers.get('If-None-Match')
    if if_none_match is None:
        return
    if if_none_match == '*' or response_etag in if_none_match:
        raise HTTPException(status_code=304, headers=response.headers)  # type: ignore[arg-type]


router = APIRouter(prefix='/api/v1')
