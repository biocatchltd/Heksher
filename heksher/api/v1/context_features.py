from typing import List

from fastapi import APIRouter, Response
from pydantic import Field
from starlette import status
from starlette.responses import PlainTextResponse

from heksher.api.v1.util import ORJSONModel, application, router as v1_router
from heksher.api.v1.validation import ContextFeatureName
from heksher.app import HeksherApp


router = APIRouter(prefix='/context_features')


class GetContextFeaturesResponse(ORJSONModel):
    context_features: List[ContextFeatureName]


@router.get('', response_model=GetContextFeaturesResponse)
async def check_context_features(app: HeksherApp = application):
    """
    Get a listing of all the context features, in their hierarchical order.
    """
    return GetContextFeaturesResponse(context_features=await app.db_logic.get_context_features())


class GetContextFeatureResponse(ORJSONModel):
    index: int


@router.get('/{name}', response_model=GetContextFeatureResponse)
async def get_context_feature(name: str, app: HeksherApp = application):
    """
    Check whether a context exists.
    """
    index = await app.db_logic.get_context_feature_index(name)
    if index is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return GetContextFeatureResponse(index=index)


@router.delete('/{name}', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_context_feature(name: str, app: HeksherApp = application):
    """
    Deletes context feature.
    """
    if await app.db_logic.get_context_feature_index(name) is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    if await app.db_logic.is_configurable_setting_from_context_features(name):
        # if there is setting configured to use the context feature, it can't be deleted
        return PlainTextResponse("context feature can't be deleted, there is at least one setting configured by it",
                                 status_code=status.HTTP_409_CONFLICT)
    await app.db_logic.delete_context_feature(name)


class PatchContextFeatureInput(ORJSONModel):
    target_cf: str = Field(
        description="the name of the context feature to move the given context feature after/before it")
    move_after: bool = Field(default=True, description="whether to move the context feature after the target,"
                                                       "default as True; to move before, set to False")


@router.patch('/{name}', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def patch_context_feature(name: str, input: PatchContextFeatureInput, app: HeksherApp = application):
    """
    Modify existing context feature's index
    """
    index_to_move = await app.db_logic.get_context_feature_index(name)
    target_index = await app.db_logic.get_context_feature_index(input.target_cf)
    if index_to_move is None or target_index is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    if index_to_move == target_index:
        return None
    if input.move_after:
        await app.db_logic.move_after_context_feature(index_to_move, target_index)
    else:  # move before target
        await app.db_logic.move_after_context_feature(index_to_move, target_index - 1)


class AddContextFeatureInput(ORJSONModel):
    context_feature: str = Field(description="the context feature name that should be added")


class AddContextFeatureOutput(ORJSONModel):
    context_feature_index: int


@router.post('', response_model=AddContextFeatureOutput, status_code=status.HTTP_201_CREATED)
async def add_context_feature(input: AddContextFeatureInput, app: HeksherApp = application):
    """
    Add a context feature, and get its index.
    """
    existing_context_feature = await app.db_logic.get_context_feature_index(input.context_feature)
    if existing_context_feature:
        return PlainTextResponse('context feature already exists', status_code=status.HTTP_409_CONFLICT)
    new_index = await app.db_logic.add_context_feature(input.context_feature)
    return AddContextFeatureOutput(context_feature_index=new_index)


v1_router.include_router(router)
