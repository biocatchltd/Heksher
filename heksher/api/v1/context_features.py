from typing import List

from fastapi import APIRouter, Response
from starlette import status

from heksher.api.v1.util import application, ORJSONModel, router as v1_router
from heksher.api.v1.validation import ContextFeatureName
from heksher.app import HeksherApp


class GetContextFeaturesResponse(ORJSONModel):
    context_features: List[ContextFeatureName]


router = APIRouter(prefix='/context_features')


@router.get('', response_model=GetContextFeaturesResponse)
async def get_context_features(app: HeksherApp = application):
    """
    get a listing of all the context features, in their hierarchical order
    """
    return GetContextFeaturesResponse(context_features=await app.db_logic.get_context_features())


@router.get('/{name}', status_code=status.HTTP_204_NO_CONTENT)
async def get_context_feature(name: str, app: HeksherApp = application):
    """
    check whether a context exists
    """
    if await app.db_logic.is_context_feature(name):
        return Response()
    return Response(status_code=status.HTTP_404_NOT_FOUND)


v1_router.include_router(router)
