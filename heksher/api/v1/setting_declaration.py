from asyncio import gather
from dataclasses import dataclass
from itertools import chain
from logging import getLogger
from typing import Any, Dict, List, Optional, Union, Literal

import orjson
from fastapi import HTTPException
from pydantic import Field, root_validator
from starlette import status
from starlette.responses import PlainTextResponse

from heksher.api.v1.util import ORJSONModel, application, PydanticResponse
from heksher.api.v1.validation import ContextFeatureName, MetadataKey, SettingName
from heksher.app import HeksherApp
from heksher.db_logic.setting import SettingSpec
from heksher.db_logic.util import parse_setting_version
from heksher.setting_types import SettingType, setting_type

logger = getLogger(__name__)


class DeclareSettingInput(ORJSONModel):
    name: SettingName = Field(description="the name of the setting")
    configurable_features: List[ContextFeatureName] = Field(
        description="a list of context features that the setting should allow rules to match by"
    )
    type: SettingType = Field(description="the type of the setting")
    default_value: Any = Field(description="the default value of the rule, must be applicable to the setting's value")
    metadata: Dict[MetadataKey, Any] = Field(default_factory=dict, description="user-defined metadata of the setting")
    alias: Optional[SettingName] = Field(
        description="an alias for the setting name, that can be used interchangeably with the original name"
    )
    version: str = Field('1.0',
                         description="the version of the setting",
                         regex=r'^[0-9]+\.[0-9]+$')

    @root_validator(skip_on_failure=True)
    @classmethod
    def default_value_matches(cls, values: Dict[str, Any]):
        default = values['default_value']
        if default is None:
            return values
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


class UpToDateDeclareSettingOutput(ORJSONModel):
    outcome: Literal['created', 'uptodate'] = Field(description="'created' if the setting is newly created, or "
                                                                "'uptodate' if it already existed at the same version")


class OutdatedDeclareSettingOutput(ORJSONModel):
    outcome: Literal['outdated'] = Field('outdated', description="'outdated' if the setting is already defined at a"
                                                                 " higher version")
    latest_version: str = Field(description="the latest version of the setting")
    differences: List[str] = Field(description="a list of differences between the declaration and the setting "
                                               "attributes")


class UpgradeDeclareSettingOutput(ORJSONModel):
    outcome: Literal['upgraded', 'rejected'] = Field(description="'upgraded' if the setting was successfully upgraded, "
                                                                 "'rejected' if the upgrade was rejected due to "
                                                                 "breaking changes")
    previous_version: str = Field(description="the previous version of the setting")
    differences: List[str] = Field(description="a list of changes made to the setting attributes")


class MismatchDeclareSettingOutput(ORJSONModel):
    outcome: Literal['mismatch'] = Field('mismatch', description="'mismatch' if the setting was declared at the same "
                                                                 "version, but with different attributes")
    differences: List[str] = Field(description="a list of differences between the declaration and the setting")


@dataclass
class Difference:
    scale: Literal['minor', 'major', 'mismatch']
    description: str

    def __str__(self):
        return f'{self.scale}: {self.description}'


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
            if alias_canonical_name:
                return PlainTextResponse(f"alias '{input.alias}' used by another setting",
                                         status_code=status.HTTP_409_CONFLICT)
            logger.info('creating new setting', extra={'setting_name': input.name})
            aliases = [input.alias] if input.alias else None
            raw_default_value = str(orjson.dumps(input.default_value), 'utf-8')
            spec = SettingSpec(input.name, str(input.type), raw_default_value, input.metadata,
                               input.configurable_features, aliases, input.version)
            await app.db_logic.add_setting(spec)
            return PydanticResponse(UpToDateDeclareSettingOutput(outcome='created'))
    elif input.alias and input.alias not in existing.all_names:
        return PlainTextResponse(f"alias '{input.alias}' is not a known alias of existing setting '{existing.name}'",
                                 status_code=status.HTTP_409_CONFLICT)

    differences: Dict[Literal['minor', 'major', 'mismatch'], List[str]] = {k: [] for k in
                                                                           ['minor', 'major', 'mismatch']}

    # all the functions below handle different attributes of the setting. They append the differences to the dict,
    # and return True if there are any differences.

    async def handle_cf_diff() -> bool:
        existing_setting_cfs = frozenset(existing.configurable_features)
        new_setting_cfs = frozenset(input.configurable_features)
        if existing_setting_cfs == new_setting_cfs:
            return False
        removed_cfs = existing_setting_cfs - new_setting_cfs
        if removed_cfs:
            actual_cfs_in_use = await app.db_logic.get_actual_configurable_features(existing.name)
            removed_cfs_in_use = removed_cfs & actual_cfs_in_use.keys()
            if removed_cfs_in_use:
                rule_ids = list(chain.from_iterable(actual_cfs_in_use[cf] for cf in removed_cfs_in_use))
                differences['mismatch'].append(
                    f'configurable features {removed_cfs} are still in use by rules {rule_ids}')
                return True
        if existing_setting_cfs > new_setting_cfs:
            differences['minor'].append(f'removal of configurable features {sorted(removed_cfs)}')
        else:
            not_cf = await app.db_logic.get_not_found_context_features(new_setting_cfs)
            if not_cf:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                    detail=f'{not_cf} are not acceptable context features')
            differences['major'].append(f'change of configurable features from {existing_setting_cfs} '
                                        f'to {new_setting_cfs}')
        return True

    async def handle_type_diff() -> bool:
        if existing.type == input.type:
            return False
        if input.type < existing.type:
            differences['minor'].append(f'change of type from {existing.type} to subtype {input.type}')
        else:
            rules = await app.db_logic.get_rules_for_setting(input.name)
            mismatched_rule_ids = [rule.rule_id for rule in rules if not input.type.validate(rule.value)]
            if mismatched_rule_ids:
                differences['mismatch'].append(f'setting type incompatible with values for rules: '
                                               f'{sorted(mismatched_rule_ids)}')
            else:
                differences['major'].append(f'change of type from {existing.type} to {input.type}')
        return True

    def handle_rename() -> bool:
        if input.name == existing.name:
            # the names are equal, and we have a guarantee that the alias is already an alias of the setting
            return False
        assert input.alias == existing.name
        differences['minor'].append(f'rename of setting from {existing.name} to {input.name}')
        return True

    def handle_default_value_diff() -> bool:
        if existing.default_value == input.default_value:
            return False
        differences['minor'].append(f'change of default value from {existing.default_value} to {input.default_value}')
        return True

    def handle_metadata_diff() -> bool:
        if existing.metadata == input.metadata:
            return False
        all_keys = existing.metadata.keys() | input.metadata.keys()
        for key in all_keys:
            if key not in existing.metadata:
                # by necessity the key must be in the input
                differences['minor'].append(f'addition of metadata key {key} {input.metadata[key]}')
            elif key not in input.metadata:
                # by necessity the key must be in the existing
                differences['minor'].append(f'removal of metadata key {key}')
            elif existing.metadata[key] != input.metadata[key]:
                differences['minor'].append(f'change of metadata key {key} from {existing.metadata[key]} '
                                            f'to {input.metadata[key]}')
        return True

    is_cf_diff, is_type_diff = await gather(handle_cf_diff(), handle_type_diff())
    new_cfs = input.configurable_features if is_cf_diff else None
    new_type = input.type if is_type_diff else None
    new_name = input.name if handle_rename() else None
    new_default_value = input.default_value if handle_default_value_diff() else None
    new_metadata = input.metadata if handle_metadata_diff() else None

    any_changes = (
            new_cfs is not None
            or new_type is not None
            or new_name is not None
            or new_default_value is not None
            or new_metadata is not None
    )

    diff_list = differences['mismatch'] + differences['major'] + differences['minor']
    if input.version == existing.version:
        if any_changes:
            return PydanticResponse(MismatchDeclareSettingOutput(differences=diff_list),
                                    status_code=status.HTTP_409_CONFLICT)
        return PydanticResponse(UpToDateDeclareSettingOutput(outcome='uptodate'))

    input_version = parse_setting_version(input.version)
    existing_version = parse_setting_version(existing.version)

    if input_version < existing_version:
        return PydanticResponse(OutdatedDeclareSettingOutput(latest_version=existing.version,
                                                             differences=diff_list))

    # now the user is definitely attempting an upgrade
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
            UpgradeDeclareSettingOutput(outcome='rejected', previous_version=existing.version, differences=diff_list),
            status_code=status.HTTP_409_CONFLICT)
    await app.db_logic.update_setting(existing.name, new_name, new_cfs, new_type, new_default_value,
                                      new_metadata, input.version)
    return PydanticResponse(UpgradeDeclareSettingOutput(outcome='upgraded', previous_version=existing.version,
                                                        differences=diff_list))


declare_setting_enpoint_args = dict(
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
