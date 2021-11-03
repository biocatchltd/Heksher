import json

from pytest import fixture, mark, raises
from requests import HTTPError


@mark.asyncio
async def test_declare_new_setting(size_limit_setting, app_client):
    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'aliases': []
    }


@mark.asyncio
@mark.parametrize('type_', [15, 'Flags{1,2,3}', 'enum[1,2,3]', 'Flags[[0]]', 'Flags[]'])
async def test_declare_new_setting_bad_type(app_client, type_):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': type_,
        'default_value': 200.5,
        'metadata': {'testing': True}
    }))
    assert res.status_code == 422


@mark.asyncio
async def test_declare_new_setting_bad_default(app_client):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200.5,
        'metadata': {'testing': True}
    }))
    assert res.status_code == 422


@mark.asyncio
async def test_declare_new_setting_bad_cf(app_client):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme', 'color'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True}
    }))
    assert res.status_code == 422


@mark.asyncio
async def test_declare_new_setting_modify_bad_cf(size_limit_setting, app_client):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme', 'color'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True}
    }))
    assert res.status_code == 422


@mark.asyncio
async def test_declare_no_modify(size_limit_setting, app_client):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True}
    }))
    res.raise_for_status()
    assert res.json() == {
        'created': False,
        'changed': [],
        'incomplete': {}
    }


@mark.asyncio
async def test_declare_modify(app_client):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True, 'ctr': 1, 'dummy': 2}
    }))
    res.raise_for_status()
    assert res.json() == {
        'created': True,
        'changed': [],
        'incomplete': {}
    }

    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 300,
        'metadata': {'testing': True, 'ctr': 2}
    }))
    res.raise_for_status()
    assert res.json() == {
        'created': False,
        'changed': [
            'configurable_features',
            'default_value',
            'metadata.ctr',
            'metadata.dummy',
        ],
        'incomplete': {}
    }

    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 300,
        'metadata': {'testing': True, 'ctr': 2},
        'aliases': []
    }


@mark.asyncio
async def test_declare_conflict(size_limit_setting, app_client):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'str',
        'default_value': "200",
        'metadata': {'testing': True}
    }))
    assert res.status_code == 409


@mark.asyncio
async def test_declare_type_upgrade(size_limit_setting, app_client):
    upgraded_type = 'float'
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': upgraded_type,
        'default_value': 200,
        'metadata': {'testing': True}
    }))
    res.raise_for_status()
    assert res.json() == {'changed': ['type'], 'created': False, 'incomplete': {}}

    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': upgraded_type,
        'default_value': 200,
        'metadata': {'testing': True},
        'aliases': [],
    }


@mark.asyncio
async def test_declare_incomplete(size_limit_setting, app_client):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True}
    }))
    res.raise_for_status()
    assert res.json() == {
        'created': False,
        'changed': [],
        'incomplete': {
            'configurable_features': ['user', 'theme']
        }
    }

    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'aliases': [],
    }


@mark.asyncio
async def test_get_setting(size_limit_setting, app_client):
    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'aliases': [],
    }


@mark.asyncio
async def test_get_setting_missing(app_client):
    res = await app_client.get('/api/v1/settings/size_limit')
    assert res.status_code == 404


@mark.asyncio
async def test_delete_setting(size_limit_setting, app_client):
    res = await app_client.delete('/api/v1/settings/size_limit')
    assert res.status_code == 204
    assert not res.content
    res = await app_client.get('/api/v1/settings/size_limit')
    assert res.status_code == 404


@mark.asyncio
async def test_delete_setting_missing(size_limit_setting, app_client):
    res = await app_client.delete('/api/v1/settings/size_limit2')
    assert res.status_code == 404


@mark.asyncio
@mark.parametrize('additional_data', [False, None])
async def test_get_settings(app_client, additional_data):
    async def mk_setting(name: str):
        res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
            'name': name,
            'configurable_features': [],
            'type': 'int'
        }))
        res.raise_for_status()
        assert res.json() == {
            'created': True,
            'changed': [],
            'incomplete': {}
        }

    await mk_setting('a')
    await mk_setting('c')
    await mk_setting('b')

    request_data = {}
    if additional_data is not None:
        request_data['include_additional_data'] = additional_data

    res = await app_client.get('/api/v1/settings', data=json.dumps(request_data))
    res.raise_for_status()
    assert res.json() == {
        'settings': [
            {'name': 'a'},
            {'name': 'b'},
            {'name': 'c'},
        ]
    }


@mark.asyncio
async def test_get_settings_additional_data(app_client):
    async def mk_setting(name: str, type: str):
        res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
            'name': name,
            'configurable_features': ['theme', 'user'],
            'type': type
        }))
        res.raise_for_status()
        assert res.json() == {
            'created': True,
            'changed': [],
            'incomplete': {}
        }

    await mk_setting('a', 'int')
    await mk_setting('c', 'float')
    await mk_setting('b', 'str')

    res = await app_client.get('/api/v1/settings', query_string={
        'include_additional_data': True
    })
    res.raise_for_status()
    assert res.json() == {
        'settings': [
            {'name': 'a', 'type': 'int', 'configurable_features': ['user', 'theme'],
             'metadata': {}, 'default_value': None, 'aliases': []},
            {'name': 'b', 'type': 'str', 'configurable_features': ['user', 'theme'],
             'metadata': {}, 'default_value': None, 'aliases': []},
            {'name': 'c', 'type': 'float', 'configurable_features': ['user', 'theme'],
             'metadata': {}, 'default_value': None, 'aliases': []},
        ]
    }


@fixture
async def interval_setting(app_client):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'interval',
        'configurable_features': ['user', 'theme'],
        'type': 'float',
        'default_value': 5,
        'metadata': {'testing': True}
    }))
    res.raise_for_status()
    assert res.json() == {
        'created': True,
        'changed': [],
        'incomplete': {}
    }


@mark.asyncio
@mark.parametrize('new_type', ['float', 'int'])
async def test_type_downgrade_no_rules(interval_setting, app_client, new_type):
    res = await app_client.put('/api/v1/settings/interval/type', json={
        'type': new_type
    })
    assert res.status_code == 204
    assert not res.content

    res = await app_client.get('/api/v1/settings/interval')
    res.raise_for_status()
    resp_json = res.json()
    assert resp_json['type'] == new_type
    assert resp_json['default_value'] == 5


@mark.asyncio
async def test_type_downgrade_no_rules_default_conflict(interval_setting, app_client):
    res = await app_client.put('/api/v1/settings/interval/type', json={
        'type': 'bool'
    })
    assert res.status_code == 409
    assert sum('default value' in reason for reason in res.json()['conflicts']) == 1

    res = await app_client.get('/api/v1/settings/interval')
    res.raise_for_status()
    resp_json = res.json()
    assert resp_json['type'] == 'float'
    assert resp_json['default_value'] == 5


@mark.asyncio
async def test_type_downgrade_with_rules(interval_setting, app_client):
    res = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'interval',
        'feature_values': {'theme': 'bright', 'user': 'me'},
        'value': 10,
        'metadata': {'test': True}
    }))
    res.raise_for_status()

    res = await app_client.put('/api/v1/settings/interval/type', json={
        'type': 'int'
    })
    assert res.status_code == 204
    assert not res.content

    res = await app_client.get('/api/v1/settings/interval')
    res.raise_for_status()
    resp_json = res.json()
    assert resp_json['type'] == 'int'
    assert resp_json['default_value'] == 5


@mark.asyncio
async def test_declare_downgrade_with_rules_conflict(interval_setting, app_client):
    res = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'interval',
        'feature_values': {'theme': 'bright', 'user': 'me'},
        'value': 10.6,
        'metadata': {'test': True}
    }))
    res.raise_for_status()
    j_result = res.json()
    rule_id = j_result.pop('rule_id')

    res = await app_client.put('/api/v1/settings/interval/type', json={
        'type': 'int'
    })
    assert res.status_code == 409
    assert sum(str(rule_id) in reason for reason in res.json()['conflicts']) == 1

    res = await app_client.get('/api/v1/settings/interval')
    res.raise_for_status()
    resp_json = res.json()
    assert resp_json['type'] == 'float'
    assert resp_json['default_value'] == 5


@mark.asyncio
@mark.parametrize('new_type', ['float', 'int'])
async def test_type_downgrade_missing(interval_setting, app_client, new_type):
    res = await app_client.put('/api/v1/settings/intervalloo/type', json={
        'type': new_type
    })
    assert res.status_code == 404


@mark.asyncio
async def test_type_downgrade_with_rules_enum(app_client):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'background_color',
        'configurable_features': ['theme'],
        'type': 'Enum["red", "blue", "green"]',
        'default_value': "blue",
        'metadata': {'testing': True}
    }))
    res.raise_for_status()
    assert res.json() == {
        'created': True,
        'changed': [],
        'incomplete': {}
    }

    res = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'background_color',
        'feature_values': {'theme': 'bright'},
        'value': "green",
        'metadata': {'test': True}
    }))
    res.raise_for_status()

    res = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'background_color',
        'feature_values': {'theme': 'dark'},
        'value': "blue",
        'metadata': {'test': True}
    }))
    res.raise_for_status()

    res = await app_client.put('/api/v1/settings/background_color/type', json={
        'type': 'Enum["blue", "green", "yellow"]'
    })
    assert res.status_code == 204
    assert not res.content

    res = await app_client.get('/api/v1/settings/background_color')
    res.raise_for_status()
    resp_json = res.json()
    assert resp_json['type'] == 'Enum["blue","green","yellow"]'
    assert resp_json['default_value'] == "blue"


@mark.asyncio
async def test_type_downgrade_with_rules_enum_bad(app_client):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'background_color',
        'configurable_features': ['theme'],
        'type': 'Enum["red", "blue", "green"]',
        'default_value': "blue",
        'metadata': {'testing': True}
    }))
    res.raise_for_status()
    assert res.json() == {
        'created': True,
        'changed': [],
        'incomplete': {}
    }

    res = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'background_color',
        'feature_values': {'theme': 'bright'},
        'value': "green",
        'metadata': {'test': True}
    }))
    res.raise_for_status()

    res = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'background_color',
        'feature_values': {'theme': 'dark'},
        'value': "red",
        'metadata': {'test': True}
    }))
    res.raise_for_status()

    res = await app_client.put('/api/v1/settings/background_color/type', json={
        'type': 'Enum["blue", "green", "yellow"]'
    })
    assert res.status_code == 409

    res = await app_client.get('/api/v1/settings/background_color')
    res.raise_for_status()
    resp_json = res.json()
    assert resp_json['type'] == 'Enum["blue","green","red"]'
    assert resp_json['default_value'] == "blue"


@mark.asyncio
@mark.parametrize('old,new', [
    ('A', 'Z'),
    ('A1', 'Z'),
])
async def test_rename_setting(app_client, old, new):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'A',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'alias': 'A1'
    }))
    res.raise_for_status()
    res = await app_client.put(f'/api/v1/settings/{old}', data=json.dumps({'new_name': new}))
    res.raise_for_status()
    res = await app_client.get('/api/v1/settings/Z')
    res.raise_for_status()
    data = res.json()
    assert data['name'] == 'Z'
    assert set(data['aliases']) == {'A', 'A1'}


@mark.asyncio
@mark.parametrize('old,new', [
    ('A', 'A'),
    ('A1', 'A'),
])
async def test_rename_setting_no_action_needed(app_client, old, new):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'A',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'alias': 'A1'
    }))
    res.raise_for_status()
    res = await app_client.put(f'/api/v1/settings/{old}', data=json.dumps({'new_name': new}))
    res.raise_for_status()
    res = await app_client.get('/api/v1/settings/A')
    res.raise_for_status()
    data = res.json()
    assert data['name'] == 'A'
    assert set(data['aliases']) == {'A1'}


@mark.asyncio
@mark.parametrize('old,new', [
    ('A', 'A1'),
    ('A1', 'A1'),
])
async def test_rename_setting_to_alias(app_client, old, new):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'A',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'alias': 'A1'
    }))
    res.raise_for_status()
    res = await app_client.put(f'/api/v1/settings/{old}', data=json.dumps({'new_name': new}))
    res.raise_for_status()
    res = await app_client.get('/api/v1/settings/A1')
    res.raise_for_status()
    data = res.json()
    assert data['name'] == 'A1'
    assert set(data['aliases']) == {'A'}


@mark.asyncio
@mark.parametrize('old,new', [
    ('A', 'B'),
    ('A', 'B1'),
    ('A1', 'B'),
    ('A1', 'B1'),
])
async def test_rename_setting_existing(app_client, old, new):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'A',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'alias': 'A1'
    }))
    res.raise_for_status()
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'B',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'alias': 'B1'
    }))
    res.raise_for_status()
    res = await app_client.put(f'/api/v1/settings/{old}', data=json.dumps({'new_name': new}))
    with raises(HTTPError):
        res.raise_for_status()
    res = await app_client.get('/api/v1/settings/A')
    res.raise_for_status()
    data = res.json()
    assert data['name'] == 'A'
    assert set(data['aliases']) == {'A1'}
    res = await app_client.get('/api/v1/settings/B')
    res.raise_for_status()
    data = res.json()
    assert data['name'] == 'B'
    assert set(data['aliases']) == {'B1'}


@mark.asyncio
async def test_rename_setting_not_existing(app_client):
    res = await app_client.put('/api/v1/settings/X', data=json.dumps({'new_name': 'Y'}))
    with raises(HTTPError):
        res.raise_for_status()


@mark.asyncio
async def test_rename_setting_cascade(app_client):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'A',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
    }))
    res.raise_for_status()
    res = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'A',
        'feature_values': {'theme': 'dark'},
        'value': 10,
        'metadata': {'testing': True}
    }))
    res.raise_for_status()
    rule_id = res.json()["rule_id"]
    res = await app_client.put('/api/v1/settings/A', data=json.dumps({'new_name': 'Z'}))
    res.raise_for_status()
    res = await app_client.get(f'/api/v1/rules/{rule_id}')
    res.raise_for_status()
    assert res.json()["setting"] == "Z"
