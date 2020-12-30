from typing import List

from heksher.api.v1.util import router, application, ORJSONModel
from heksher.app import HeksherApp


class GetContextFeaturesResponse(ORJSONModel):
    context_features: List[str]


@router.get('/context_features', response_model=GetContextFeaturesResponse)
async def get_context_features(app: HeksherApp = application):
    return GetContextFeaturesResponse(context_features=await app.db_logic.get_context_features())
