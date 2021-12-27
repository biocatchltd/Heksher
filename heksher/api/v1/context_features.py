from typing import List, Union

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
    Returns the index of the context feature; If it doesn't exists, returns status code 404.
    """
    index = await app.db_logic.get_context_feature_index(name)
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
    if await app.db_logic.get_context_feature_index(name) is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    if await app.db_logic.is_configurable_setting_from_context_features(name):
        # if there is setting configured to use the context feature, it can't be deleted
        return PlainTextResponse("context feature can't be deleted, there is at least one setting configured by it",
                                 status_code=status.HTTP_409_CONFLICT)
    await app.db_logic.delete_context_feature(name)


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
    index_to_move = await app.db_logic.get_context_feature_index(name)
    target_index = await app.db_logic.get_context_feature_index(input.target)
    if index_to_move is None or target_index is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    if isinstance(input, PatchBeforeContextFeatureInput):
        target_index -= 1
    if index_to_move == target_index:
        return None
    await app.db_logic.move_after_context_feature(index_to_move, target_index)


class AddContextFeatureInput(ORJSONModel):
    context_feature: str = Field(description="the context feature name that should be added")


@router.post('', response_class=Response, status_code=status.HTTP_204_NO_CONTENT)
async def add_context_feature(input: AddContextFeatureInput, app: HeksherApp = application):
    """
    Add a context feature to the end of the context features.
    """
    existing_context_feature = await app.db_logic.get_context_feature_index(input.context_feature)
    if existing_context_feature is not None:
        return PlainTextResponse('context feature already exists', status_code=status.HTTP_409_CONFLICT)
    await app.db_logic.add_context_feature(input.context_feature)


v1_router.include_router(router)
