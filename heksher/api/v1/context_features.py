from typing import List, Union

from fastapi import APIRouter, Response
from pydantic import Field
from starlette import status
from starlette.responses import PlainTextResponse

from heksher.api.v1.util import ORJSONModel, application, router as v1_router
from heksher.api.v1.validation import ContextFeatureName
from heksher.app import HeksherApp
from heksher.db_logic.context_feature import (
    db_add_context_feature_to_end, db_delete_context_feature, db_get_context_feature_index, db_get_context_features,
    db_is_configurable_setting_from_context_features, db_move_after_context_feature
)

router = APIRouter(prefix='/context_features')


class GetContextFeaturesResponse(ORJSONModel):
    context_features: List[ContextFeatureName]


@router.get('', response_model=GetContextFeaturesResponse)
async def check_context_features(app: HeksherApp = application):
    """
    Get a listing of all the context features, in their hierarchical order.
    """
    async with app.engine.begin() as conn:
        cfs = await db_get_context_features(conn)
    return GetContextFeaturesResponse(context_features=(name for (name, _) in cfs))


class GetContextFeatureResponse(ORJSONModel):
    index: int


@router.get('/{name}', response_model=GetContextFeatureResponse)
async def get_context_feature(name: str, app: HeksherApp = application):
    """
    Returns the index of the context feature; If it doesn't exists, returns status code 404.
    """
    async with app.engine.begin() as conn:
        index = await db_get_context_feature_index(conn, name)
    if index is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return GetContextFeatureResponse(index=index)


@router.delete('/{name}', status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
               responses={
                   status.HTTP_409_CONFLICT: {
                       "description": "context feature is in use",
                   }
               }
               )
async def delete_context_feature(name: str, app: HeksherApp = application):
    """
    Deletes context feature.
    """
    async with app.engine.begin() as conn:
        if await db_get_context_feature_index(conn, name) is None:
            return Response(status_code=status.HTTP_404_NOT_FOUND)
        if await db_is_configurable_setting_from_context_features(conn, name):
            # if there is setting configured to use the context feature, it can't be deleted
            return PlainTextResponse("context feature can't be deleted, there is at least one setting configured by it",
                                     status_code=status.HTTP_409_CONFLICT)
        await db_delete_context_feature(conn, name)


class PatchAfterContextFeatureInput(ORJSONModel):
    to_after: str = Field(
        description="the name of the context feature to move after the given context feature")

    @property
    def target(self) -> str:
        return self.to_after


class PatchBeforeContextFeatureInput(ORJSONModel):
    to_before: str = Field(
        description="the name of the context feature to move before the given context feature")

    @property
    def target(self) -> str:
        return self.to_before


@router.patch('/{name}/index', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def patch_context_feature(name: str, input: Union[PatchAfterContextFeatureInput, PatchBeforeContextFeatureInput],
                                app: HeksherApp = application):
    """
    Modify existing context feature's index
    """
    async with app.engine.begin() as conn:
        index_to_move = await db_get_context_feature_index(conn, name)
        target_index = await db_get_context_feature_index(conn, input.target)
        if index_to_move is None or target_index is None:
            return Response(status_code=status.HTTP_404_NOT_FOUND)
        if isinstance(input, PatchBeforeContextFeatureInput):
            target_index -= 1
        if index_to_move == target_index:
            return None
        await db_move_after_context_feature(conn, index_to_move, target_index)


class AddContextFeatureInput(ORJSONModel):
    context_feature: str = Field(description="the context feature name that should be added")


@router.post('', response_class=Response, status_code=status.HTTP_204_NO_CONTENT)
async def add_context_feature(input: AddContextFeatureInput, app: HeksherApp = application):
    """
    Add a context feature to the end of the context features.
    """
    async with app.engine.begin() as conn:
        existing_context_feature = await db_get_context_feature_index(conn, input.context_feature)
        if existing_context_feature is not None:
            return PlainTextResponse('context feature already exists', status_code=status.HTTP_409_CONFLICT)
        await db_add_context_feature_to_end(conn, input.context_feature)


v1_router.include_router(router)
