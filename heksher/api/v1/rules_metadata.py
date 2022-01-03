from logging import getLogger
from typing import Any, Dict, Optional

from fastapi import APIRouter, Response
from pydantic import Field
from starlette import status

from heksher.api.v1.util import ORJSONModel, application
from heksher.api.v1.validation import MetadataKey
from heksher.app import HeksherApp

router = APIRouter()
logger = getLogger(__name__)


class InputRuleMetadata(ORJSONModel):
    metadata: Dict[MetadataKey, Any] = Field(default_factory=dict, description="user-defined metadata of the rule")


@router.post('/{rule_id}/metadata', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def update_rule_metadata(rule_id: int, input: InputRuleMetadata, app: HeksherApp = application):
    """
    Update the rule's metadata
    """
    if not input.metadata:
        return None
    if not await app.db_logic.get_rule(rule_id, include_metadata=False):
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    await app.db_logic.update_rule_metadata(rule_id, input.metadata)


@router.put('/{rule_id}/metadata', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def replace_rule_metadata(rule_id: int, input: InputRuleMetadata, app: HeksherApp = application):
    """
    Change the current metadata of the rule.
    """
    if not await app.db_logic.get_rule(rule_id, include_metadata=False):
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    if not input.metadata:
        # empty dictionary equals to deleting the metadata
        await app.db_logic.delete_rule_metadata(rule_id)
    else:
        await app.db_logic.replace_rule_metadata(rule_id, input.metadata)


class PutRuleMetadataKey(ORJSONModel):
    value: Any = Field(..., description="the new value of the given key and rule in the rule's metadata")


@router.put('/{rule_id}/metadata/{key}', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def update_rule_metadata_key(rule_id: int, key: MetadataKey, input: PutRuleMetadataKey,
                                   app: HeksherApp = application):
    """
    Updates the current metadata of the rule. Existing keys won't be deleted.
    """
    if not await app.db_logic.get_rule(rule_id, include_metadata=False):
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    await app.db_logic.update_rule_metadata_key(rule_id, key, input.value)


@router.delete('/{rule_id}/metadata', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_rule_metadata(rule_id: int, app: HeksherApp = application):
    """
    Delete a rule's metadata.
    """
    if not await app.db_logic.get_rule(rule_id, include_metadata=False):
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    await app.db_logic.delete_rule_metadata(rule_id)


@router.delete('/{rule_id}/metadata/{key}', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_rule_key_from_metadata(rule_id: int, key: MetadataKey, app: HeksherApp = application):
    """
    Delete a specific key from the rule's metadata.
    """
    if not await app.db_logic.get_rule(rule_id, include_metadata=False):
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    await app.db_logic.delete_rule_metadata_key(rule_id, key)


class GetRuleMetadataOutput(ORJSONModel):
    metadata: Optional[Dict[MetadataKey, Any]] = Field(default_factory=dict,
                                                       description="user-defined metadata of the rule")


@router.get('/{rule_id}/metadata', response_model=GetRuleMetadataOutput,
            responses={
                status.HTTP_404_NOT_FOUND: {
                    "description": "The rule does not exist.",
                }
            })
async def get_rule_metadata(rule_id: int, app: HeksherApp = application):
    """
    Get metadata of a rule.
    """
    if not (rule := await app.db_logic.get_rule(rule_id, include_metadata=True)):
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return GetRuleMetadataOutput(metadata=rule.metadata)
