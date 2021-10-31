import json
from typing import Iterable

from pytest import fixture, mark, raises


@fixture
def default_declare_params() -> dict:
    return {
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 5,
        'metadata': {'testing': True},
    }


async def _call(coro):
    resp = await coro
    resp.raise_for_status()
    return resp.json() if resp.content else None


@mark.asyncio
async def test_settings(app_client, default_declare_params):
    async def declare(name: str, alias: str):
        default_declare_params.update({'name': name, 'alias': alias})
        return await _call(app_client.put('/api/v1/settings/declare', data=json.dumps(default_declare_params)))

    async def get(name_or_alias: str):
        return await _call(app_client.get(f'/api/v1/settings/{name_or_alias}'))

    async def get_all():
        return await _call(app_client.get('/api/v1/settings'))

    async def get_all_full():
        return await _call(app_client.get('/api/v1/settings', query_string={'include_additional_data': True}))

    assert (await declare('god', 'elohim'))['created'] is True
    res = await get('elohim')
    assert res['name'] == "god"
    assert res['aliases'] == ["elohim"]
    assert await get('god') == await get('elohim')
    res = await declare('elohim', 'yahweh')
    assert res['created'] is False
    assert res['changed'] == ['alias']
    res = await get('yahweh')
    assert res['name'] == "god"
    assert res['aliases'] == ["elohim", "yahweh"]
    assert (await declare('moses', 'moshe'))['created'] is True
    await _call(app_client.put(f'/api/v1/settings/moshe/type', data=json.dumps({'type': 'float'})))
    assert (await get('moshe'))['type'] == "float"

    assert (await get_all())["settings"] == [{"name": "god"}, {"name": "moses"}]
    assert (await get_all_full())["settings"] == [
        {'name': 'god', 'configurable_features': ['user', 'theme'], 'type': 'int', 'default_value': 5,
         'metadata': {'testing': True}, 'aliases': ['elohim', 'yahweh']},
        {'name': 'moses', 'configurable_features': ['user', 'theme'], 'type': 'float', 'default_value': 5,
         'metadata': {'testing': True}, 'aliases': ['moshe']}
    ]

    await _call(app_client.delete(f'/api/v1/settings/moshe'))
    assert (await get_all())["settings"] == [{"name": "god"}]


@mark.asyncio
async def test_rules(app_client, default_declare_params):
    async def add(setting: str, theme: str):
        return await _call(app_client.post('/api/v1/rules', data=json.dumps({
            'setting': setting,
            'feature_values': {'theme': theme},
            'value': 10,
            'metadata': {'testing': True}
        })))

    async def search(setting: str, theme: str):
        return await _call(app_client.post('/api/v1/rules/search', data=json.dumps({
            'setting': setting,
            'feature_values': {'theme': theme},
        })))

    async def query(*settings: Iterable[str]):
        return await _call(app_client.post('/api/v1/rules/query', data=json.dumps({
            'setting_names': settings,
            'context_features_options': "*",
        })))

    default_declare_params.update({'name': 'cat', 'alias': 'hatul'})
    await _call(app_client.put('/api/v1/settings/declare', data=json.dumps(default_declare_params)))
    default_declare_params.update({'name': 'dog', 'alias': 'kelev'})
    await _call(app_client.put('/api/v1/settings/declare', data=json.dumps(default_declare_params)))

    cat_rule = (await add('cat', 'bright'))["rule_id"]
    hatul_rule = (await add('hatul', 'dark'))["rule_id"]
    kelev_rule = (await add('kelev', 'dracula'))["rule_id"]
    assert (await search("hatul", "bright"))["rule_id"] == cat_rule
    assert (await search("hatul", "dark"))["rule_id"] == hatul_rule
    assert (await search("kelev", "dracula"))["rule_id"] == kelev_rule
    with raises(Exception):
        await query("cat", "kelev", "yanshuf")
    assert (await query("cat", "kelev"))['rules'] == {
        'cat': [{'value': 10, 'context_features': [['theme', 'bright']], 'rule_id': cat_rule},
                {'value': 10, 'context_features': [['theme', 'dark']], 'rule_id': hatul_rule}],
        'dog': [{'value': 10, 'context_features': [['theme', 'dracula']], 'rule_id': kelev_rule}]
    }


@mark.asyncio
async def test_metadata(app_client, default_declare_params):
    async def get():
        return (await _call(app_client.get('/api/v1/settings/yayin/metadata')))['metadata']

    default_declare_params.update({'name': 'wine', 'alias': 'yayin'})
    await _call(app_client.put('/api/v1/settings/declare', data=json.dumps(default_declare_params)))

    assert await get() == {'testing': True}
    await _call(app_client.post('/api/v1/settings/yayin/metadata', data=json.dumps({"metadata": {"alcohol": "6%"}})))
    assert await get() == {'testing': True, "alcohol": "6%"}
    await _call(app_client.put('/api/v1/settings/yayin/metadata', data=json.dumps({"metadata": {
        "price": 50,
        "experimenting": True,
        "should_drink": True,
    }})))
    assert await get() == {"price": 50, "experimenting": True, "should_drink": True}
    await _call(app_client.put('/api/v1/settings/yayin/metadata/should_drink', data=json.dumps({"value": False})))
    assert await get() == {"price": 50, "experimenting": True, "should_drink": False}
    await _call(app_client.delete('/api/v1/settings/yayin/metadata/should_drink'))
    assert await get() == {"price": 50, "experimenting": True}
    await _call(app_client.delete('/api/v1/settings/yayin/metadata'))
    assert await get() == {}
