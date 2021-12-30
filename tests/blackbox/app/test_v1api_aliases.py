import json
from typing import Optional

from async_asgi_testclient.response import Response
from pytest import fixture, mark, raises
from requests import HTTPError


@fixture
def default_declare_params() -> dict:
    return {
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 5,
        'metadata': {'testing': True},
    }


def _get_ok_data(response: Response):
    if not response.ok:
        raise HTTPError(f"Response is not OK {response.status_code}: {response.content}")
    return response.json() if response.content else None


@mark.asyncio
@mark.parametrize('first_version', ['1.0', None])
async def test_settings(app_client, default_declare_params, first_version):
    async def declare(name: str, alias: Optional[str], version: Optional[str]):
        params = dict(default_declare_params)
        params['name'] = name
        if alias:
            params['alias'] = alias
        if version:
            params['version'] = version
        return _get_ok_data(await app_client.post('/api/v1/settings/declare', json=params))

    async def get(name_or_alias: str):
        return _get_ok_data(await app_client.get(f'/api/v1/settings/{name_or_alias}'))

    assert (await declare('elohim', None, first_version))['outcome'] == 'created'
    assert (await declare('god', 'elohim', '1.1'))['outcome'] == 'upgraded'
    res = await get('elohim')
    assert res['name'] == "god"
    assert res['aliases'] == ["elohim"]
    assert await get('god') == await get('elohim')
    res = await declare('yahweh', 'god', '2.0')
    assert res['outcome'] == 'upgraded'
    assert res['previous_version'] == '1.1'
    assert sum(diff.startswith('rename') for diff in res['differences']) == 1
    res = await get('yahweh')
    assert res['name'] == "yahweh"
    assert res['aliases'] == ["elohim", "god"]

    assert (await get('yahweh')) == (await get('god')) == (await get('elohim'))


@mark.asyncio
async def test_rules(app_client, default_declare_params):
    async def add(setting: str, theme: str):
        return _get_ok_data(await app_client.post('/api/v1/rules', data=json.dumps({
            'setting': setting,
            'feature_values': {'theme': theme},
            'value': 10,
            'metadata': {'testing': True}
        })))

    async def search(setting: str, theme: str):
        return _get_ok_data(await app_client.get('/api/v1/rules/search', query_string={
            'setting': setting,
            'feature_values': f'theme:{theme}',
        }))

    async def query(*settings: str):
        return _get_ok_data(await app_client.get('/api/v1/rules/query', query_string={
            'settings': ','.join(settings),
            'context_filters': "*",
        }))

    default_declare_params.update({'name': 'cat'})
    resp = await app_client.post('/api/v1/settings/declare', data=json.dumps(default_declare_params))
    resp.raise_for_status()
    default_declare_params.update({'name': 'hatul', 'alias': 'cat', 'version': '1.3'})
    resp = await app_client.post('/api/v1/settings/declare', data=json.dumps(default_declare_params))
    resp.raise_for_status()

    default_declare_params.update({'name': 'dog', 'alias': None, 'version': '1.0'})
    resp = await app_client.post('/api/v1/settings/declare', data=json.dumps(default_declare_params))
    resp.raise_for_status()
    default_declare_params.update({'name': 'kelev', 'alias': 'dog', 'version': '2.6'})
    resp = await app_client.post('/api/v1/settings/declare', data=json.dumps(default_declare_params))
    resp.raise_for_status()

    cat_rule = (await add('cat', 'bright'))["rule_id"]
    hatul_rule = (await add('hatul', 'dark'))["rule_id"]
    kelev_rule = (await add('kelev', 'dracula'))["rule_id"]
    assert (await search("hatul", "bright"))["rule_id"] == (await search("cat", "bright"))["rule_id"] == cat_rule
    assert (await search("hatul", "dark"))["rule_id"] == (await search("cat", "dark"))["rule_id"] == hatul_rule
    assert (await search("kelev", "dracula"))["rule_id"] == (await search("dog", "dracula"))["rule_id"] == kelev_rule
    with raises(HTTPError):
        await query("cat", "kelev", "yanshuf")
    assert (await query("cat", "kelev"))['settings'] == {
        'hatul': {'rules': [{'value': 10, 'context_features': [['theme', 'bright']], 'rule_id': cat_rule},
                            {'value': 10, 'context_features': [['theme', 'dark']], 'rule_id': hatul_rule}]},
        'kelev': {'rules': [{'value': 10, 'context_features': [['theme', 'dracula']], 'rule_id': kelev_rule}]}
    }


@mark.asyncio
async def test_metadata(app_client, default_declare_params):
    async def get():
        return _get_ok_data(await app_client.get('/api/v1/settings/yayin/metadata'))['metadata']

    default_declare_params.update({'name': 'yayin', 'alias': None})
    _get_ok_data(await app_client.post('/api/v1/settings/declare', data=json.dumps(default_declare_params)))
    default_declare_params.update({'name': 'wine', 'alias': 'yayin', 'version': '1.1'})
    _get_ok_data(await app_client.post('/api/v1/settings/declare', data=json.dumps(default_declare_params)))

    assert await get() == {'testing': True}
    resp = await app_client.post('/api/v1/settings/yayin/metadata', data=json.dumps({"metadata": {"alcohol": "6%"}}))
    resp.raise_for_status()
    assert await get() == {'testing': True, "alcohol": "6%"}
    resp = await app_client.put('/api/v1/settings/yayin/metadata', data=json.dumps({"metadata": {
        "price": 50,
        "experimenting": True,
        "should_drink": True,
    }}))
    resp.raise_for_status()
    assert await get() == {"price": 50, "experimenting": True, "should_drink": True}
    resp = await app_client.put('/api/v1/settings/yayin/metadata/should_drink', data=json.dumps({"value": False}))
    resp.raise_for_status()
    assert await get() == {"price": 50, "experimenting": True, "should_drink": False}
    resp = await app_client.delete('/api/v1/settings/yayin/metadata/should_drink')
    resp.raise_for_status()
    assert await get() == {"price": 50, "experimenting": True}
    resp = await app_client.delete('/api/v1/settings/yayin/metadata')
    resp.raise_for_status()
    assert await get() == {}


@mark.asyncio
async def test_declare_existing_alias(app_client, default_declare_params):
    async def declare(name: str, alias: Optional[str], version: str):
        default_declare_params.update({'name': name, 'alias': alias, 'version': version})
        return _get_ok_data(await app_client.post('/api/v1/settings/declare', data=json.dumps(default_declare_params)))

    assert (await declare('god', None, '1.0'))['outcome'] == 'created'
    assert (await declare('elohim', 'god', '1.1'))['outcome'] == 'upgraded'
    with raises(HTTPError):
        await declare('dios', 'god', '1.0')
