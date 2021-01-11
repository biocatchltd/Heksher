from typing import List

from fastapi import APIRouter, Response
from starlette import status

from heksher.api.v1.util import application, ORJSONModel, router as v1_router
from heksher.app import HeksherApp


class GetContextFeaturesResponse(ORJSONModel):
    context_features: List[str]


router = APIRouter(prefix='/context_features')


@router.get('', response_model=GetContextFeaturesResponse)
async def get_context_features(app: HeksherApp = application):
    return GetContextFeaturesResponse(context_features=await app.db_logic.get_context_features())


@router.get('/{name}')
async def get_context_feature(name: str, app: HeksherApp = application):
    if await app.db_logic.is_context_feature(name):
        return Response()
    return Response(status_code=status.HTTP_404_NOT_FOUND)

v1_router.include_router(router)