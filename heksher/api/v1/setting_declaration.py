from asyncio import gather
from dataclasses import dataclass
from itertools import chain
from logging import getLogger
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

import orjson
from fastapi import HTTPException
from pydantic import Field, root_validator
from starlette import status
from starlette.responses import PlainTextResponse

from heksher.api.v1.util import ORJSONModel, PydanticResponse, application
from heksher.api.v1.validation import ContextFeatureName, MetadataKey, SettingName, SettingVersion
from heksher.app import HeksherApp
from heksher.db_logic.setting import SettingSpec
from heksher.db_logic.util import parse_setting_version
from heksher.setting_types import SettingType

logger = getLogger(__name__)


class DeclareSettingInput(ORJSONModel):
    name: SettingName = Field(description="the name of the setting")
    configurable_features: List[ContextFeatureName] = Field(
        description="a list of context features that the setting should allow rules to match by", min_items=1,
        unique=True
    )
    type: SettingType = Field(description="the type of the setting")
    default_value: Any = Field(..., description="the default value of the rule, must be applicable to the setting's "
                                                "value")
    metadata: Dict[MetadataKey, Any] = Field(default_factory=dict, description="user-defined metadata of the setting")
    alias: Optional[SettingName] = Field(
        description="an alias for the setting name, that can be used interchangeably with the original name"
    )
    version: SettingVersion = Field('1.0', description="the version of the setting")

    @root_validator(skip_on_failure=True)
    @classmethod
    def default_value_matches(cls, values: Dict[str, Any]):
        default = values['default_value']
        type_: SettingType = values['type']
        if not type_.validate(default):
            raise TypeError(f'type ({type_}) and default value ({default}) must match')
        return values

    @root_validator(skip_on_failure=True)
    @classmethod
    def alias_and_name_differ(cls, values: Dict[str, Any]):
        alias = values['alias']
        if alias is None:
            return values
        name = values['name']
        if name == alias:
            raise ValueError(f'name ({name}) and alias ({alias}) must differ')
        return values


class AttributeDifferenceOutput(ORJSONModel):
    level: Literal['minor', 'major', 'mismatch'] = Field(description="the level of difference")
    attribute: str = Field(description="the attribute that is different")
    latest_value: Any = Field(description="the value of the attribute in the latest declaration")


class MessageDifferenceOutput(ORJSONModel):
    level: Literal['minor', 'major', 'mismatch'] = Field(description="the level of difference")
    message: str = Field(description="message describing the difference")


class UpToDateDeclareSettingOutput(ORJSONModel):
    outcome: Literal['created', 'uptodate'] = Field(description="'created' if the setting is newly created, or "
                                                                "'uptodate' if it already existed at the same version")


class OutdatedDeclareSettingOutput(ORJSONModel):
    outcome: Literal['outdated'] = Field('outdated', description="'outdated' if the setting is already defined at a"
                                                                 " higher version")
    latest_version: str = Field(description="the latest version of the setting")
    differences: List[Union[MessageDifferenceOutput, AttributeDifferenceOutput]] = Field(
        description="a list of differences between the declaration and the setting attributes")


class UpgradeDeclareSettingOutput(ORJSONModel):
    outcome: Literal['upgraded', 'rejected'] = Field(description="'upgraded' if the setting was successfully upgraded, "
                                                                 "'rejected' if the upgrade was rejected due to "
                                                                 "breaking changes")
    previous_version: str = Field(description="the previous version of the setting")
    differences: List[Union[MessageDifferenceOutput, AttributeDifferenceOutput]] = Field(
        description="a list of differences between the declaration and the setting attributes")


class MismatchDeclareSettingOutput(ORJSONModel):
    outcome: Literal['mismatch'] = Field('mismatch', description="'mismatch' if the setting was declared at the same "
                                                                 "version, but with different attributes")
    differences: List[Union[MessageDifferenceOutput, AttributeDifferenceOutput]] = Field(
        description="a list of differences between the declaration and the setting attributes")


@dataclass
class AttrDifference:
    attribute: str
    latest_value: Any


@dataclass
class MessageDifference:
    message: str


# type aliases for internal logic
DifferenceCategory = Literal['minor', 'major', 'mismatch']
DifferenceSpec = Union[MessageDifference, AttrDifference]
DifferencesDict = Dict[DifferenceCategory, List[DifferenceSpec]]
NewSettingAttributes = Tuple[Optional[List[str]], Optional[SettingType], Optional[str], Optional[Any],
                             Optional[Dict[str, Any]]]


async def declare_setting_endpoint(input: DeclareSettingInput, app: HeksherApp = application):
    """
    Ensure that a setting exists, creating it if necessary.
    """
    existing = await app.db_logic.get_setting(input.name, include_aliases=True, include_metadata=True,
                                              include_configurable_features=True)
    if input.alias:
        alias_canonical_name = (await app.db_logic.get_canonical_names([input.alias]))[input.alias]
        if alias_canonical_name is None:
            raise HTTPException(status_code=404, detail=f'alias {input.alias} does not exist')
        # we only accept two options: either the alias is a canonical name and existing does nt exist, or it is an
        # existing alias of the existing setting
        if (existing or input.alias != alias_canonical_name) and (
                not existing or existing.name != alias_canonical_name):
            raise HTTPException(status_code=409, detail=f'alias {input.alias} is an alias of unrelated setting '
                                                        f'{alias_canonical_name}')
    else:
        alias_canonical_name = None

    if existing is None:
        if alias_canonical_name:
            existing = await app.db_logic.get_setting(alias_canonical_name, include_aliases=True,
                                                      include_metadata=True,
                                                      include_configurable_features=True)
        else:
            if input.version != '1.0':
                return PlainTextResponse('newly created settings must have version 1.0', status_code=400)
            not_cf = await app.db_logic.get_not_found_context_features(input.configurable_features)
            if not_cf:
                return PlainTextResponse(f'{not_cf} are not acceptable context features',
                                         status_code=status.HTTP_404_NOT_FOUND)
            logger.info('creating new setting', extra={'setting_name': input.name})
            aliases = [input.alias] if input.alias else None
            raw_default_value = str(orjson.dumps(input.default_value), 'utf-8')
            spec = SettingSpec(input.name, str(input.type), raw_default_value, input.metadata,
                               input.configurable_features, aliases, input.version)
            await app.db_logic.add_setting(spec)
            return PydanticResponse(UpToDateDeclareSettingOutput(outcome='created'))

    async def get_diffs(is_outdated: bool) -> Tuple[NewSettingAttributes, DifferencesDict]:
        differences: DifferencesDict = {k: [] for k in ['minor', 'major', 'mismatch']}  # type: ignore[misc]

        # all the functions below handle different attributes of the setting. They append the differences to the dict,
        # and return True if there are any differences.

        async def handle_cf_diff(is_outdated: bool) -> bool:
            existing_setting_cfs = frozenset(existing.configurable_features)
            new_setting_cfs = frozenset(input.configurable_features)
            if existing_setting_cfs == new_setting_cfs:
                return False
            if is_outdated:
                # all changes are flipped in direction
                existing_setting_cfs, new_setting_cfs = new_setting_cfs, existing_setting_cfs
            removed_cfs = existing_setting_cfs - new_setting_cfs
            if not is_outdated and removed_cfs:
                actual_cfs_in_use = await app.db_logic.get_actual_configurable_features(existing.name)
                removed_cfs_in_use = removed_cfs & actual_cfs_in_use.keys()
                if removed_cfs_in_use:
                    rule_ids = list(chain.from_iterable(actual_cfs_in_use[cf] for cf in removed_cfs_in_use))
                    differences['mismatch'].append(MessageDifference(
                        f'configurable features {sorted(removed_cfs)} are still in use by rules {rule_ids}'))
                    return True
            if existing_setting_cfs > new_setting_cfs:
                differences['minor'].append(
                    MessageDifference(f'removal of configurable features {sorted(removed_cfs)}'))
            else:
                if not is_outdated:
                    not_cf = await app.db_logic.get_not_found_context_features(new_setting_cfs)
                    if not_cf:
                        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                            detail=f'{not_cf} are not acceptable context features')
                differences['major'].append(AttrDifference('configurable_features', existing.configurable_features))
            return True

        async def handle_type_diff(is_outdated: bool) -> bool:
            if existing.type == input.type:
                return False
            existing_type = existing.type
            new_type = input.type
            if is_outdated:
                # all changes are flipped in direction
                existing_type, new_type = new_type, existing_type
            if new_type < existing_type:
                differences['minor'].append(AttrDifference('type', str(existing.type)))
            else:
                # only check the rules if we're not outdated
                rules = await app.db_logic.get_rules_for_setting(input.name) if not is_outdated else []
                mismatched_rule_ids = [rule.rule_id for rule in rules if not new_type.validate(rule.value)]
                if mismatched_rule_ids:
                    differences['mismatch'].append(
                        MessageDifference(f'setting type incompatible with values for rules: '
                                          f'{sorted(mismatched_rule_ids)}'))
                else:
                    differences['major'].append(AttrDifference('type', str(existing.type)))
            return True

        def handle_rename(is_outdated: bool) -> bool:
            if input.name == existing.name:
                # the names are equal, and we have a guarantee that the alias is already an alias of the setting
                return False
            if is_outdated:
                differences['minor'].append(AttrDifference('name', existing.name))
                return True
            assert input.alias == existing.name
            differences['minor'].append(AttrDifference('name', existing.name))
            return True

        def handle_default_value_diff(is_outdated: bool) -> bool:
            if existing.default_value == input.default_value:
                return False
            differences['minor'].append(AttrDifference('default_value', existing.default_value))
            return True

        def handle_metadata_diff(is_outdated: bool) -> bool:
            if existing.metadata == input.metadata:
                return False
            differences['minor'].append(AttrDifference('metadata', existing.metadata))
            return True

        is_cf_diff, is_type_diff = await gather(handle_cf_diff(is_outdated), handle_type_diff(is_outdated))
        return (input.configurable_features if is_cf_diff else None,
                input.type if is_type_diff else None,
                input.name if handle_rename(is_outdated) else None,
                input.default_value if handle_default_value_diff(is_outdated) else None,
                input.metadata if handle_metadata_diff(is_outdated) else None), differences

    def diff_list(differences: DifferencesDict) -> List[Union[MessageDifferenceOutput, AttributeDifferenceOutput]]:
        diff_list: List[Union[MessageDifferenceOutput, AttributeDifferenceOutput]] = []
        for level, diffs in differences.items():
            for diff in diffs:
                if isinstance(diff, AttrDifference):
                    diff_list.append(AttributeDifferenceOutput(level=level, attribute=diff.attribute,
                                                               latest_value=diff.latest_value))
                else:
                    diff_list.append(MessageDifferenceOutput(level=level, message=diff.message))
        return diff_list

    if input.version == existing.version:
        _, diffs = await get_diffs(False)
        if any(v for v in diffs.values()):
            return PydanticResponse(MismatchDeclareSettingOutput(differences=diff_list(diffs)),
                                    status_code=status.HTTP_409_CONFLICT)
        return PydanticResponse(UpToDateDeclareSettingOutput(outcome='uptodate'))

    input_version = parse_setting_version(input.version)
    existing_version = parse_setting_version(existing.version)

    if input_version < existing_version:
        _, diffs = await get_diffs(True)
        return PydanticResponse(OutdatedDeclareSettingOutput(latest_version=existing.version,
                                                             differences=diff_list(diffs)))

    # now the user is definitely attempting an upgrade
    (new_cfs, new_type, new_name, new_default_value, new_metadata), differences = await get_diffs(False)
    if differences['mismatch']:
        accepted = False
    elif input_version[0] > existing_version[0]:
        # we perform a major upgrade without mismatches
        accepted = True
    else:
        assert input_version[1] > existing_version[1]
        # we perform a minor upgrade, so long as there are no major differences
        accepted = not differences['major']

    if not accepted:
        return PydanticResponse(
            UpgradeDeclareSettingOutput(outcome='rejected', previous_version=existing.version,
                                        differences=diff_list(differences)),
            status_code=status.HTTP_409_CONFLICT)
    await app.db_logic.update_setting(existing.name, new_name, new_cfs, new_type, new_default_value,
                                      new_metadata, input.version)
    return PydanticResponse(UpgradeDeclareSettingOutput(outcome='upgraded', previous_version=existing.version,
                                                        differences=diff_list(differences)))


declare_setting_enpoint_args: Dict[str, Any] = dict(
    methods=['POST'],
    responses={
        status.HTTP_200_OK: {
            "model": Union[UpToDateDeclareSettingOutput, OutdatedDeclareSettingOutput,
                           UpgradeDeclareSettingOutput, MismatchDeclareSettingOutput]
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Configurable features are not acceptable.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "The given alias is used by another setting."
        },
    }
)
