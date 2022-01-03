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
        'aliases': [],
        'version': '1.0',
    }


@mark.asyncio
async def test_declare_new_setting_bad_version(app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'version': '1.1',
    }))
    assert res.status_code == 400


@mark.asyncio
@mark.parametrize('type_', [15, 'Flags{1,2,3}', 'enum[1,2,3]', 'Flags[[0]]', 'Flags[]'])
async def test_declare_new_setting_bad_type(app_client, type_):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': type_,
        'default_value': 200.5,
        'metadata': {'testing': True}
    }))
    assert res.status_code == 422


@mark.asyncio
async def test_declare_new_setting_bad_default(app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200.5,
        'metadata': {'testing': True}
    }))
    assert res.status_code == 422


@mark.asyncio
async def test_declare_new_setting_bad_cf(app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme', 'color'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True}
    }))
    assert res.status_code == 404


@mark.asyncio
async def test_declare_new_setting_modify_bad_cf(size_limit_setting, app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme', 'color'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'version': '2.0',
    }))
    assert res.status_code == 404


@mark.asyncio
async def test_declare_no_modify(size_limit_setting, app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True}
    }))
    res.raise_for_status()
    assert res.json() == {
        'outcome': 'uptodate',
    }


@mark.asyncio
async def test_declare_modify(app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True, 'ctr': 1, 'dummy': 2},
        'version': '1.0',
    }))
    res.raise_for_status()
    assert res.json() == {'outcome': 'created', }

    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 300,
        'metadata': {'testing': True, 'ctr': 2},
        'version': '2.0',
    }))
    res.raise_for_status()
    resp_body = res.json()
    assert {diff['attribute'] for diff in resp_body.pop('differences')} == {'default_value', 'metadata',
                                                                            'configurable_features'}
    assert resp_body == {
        'outcome': 'upgraded',
        'previous_version': '1.0',
    }

    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 300,
        'metadata': {'testing': True, 'ctr': 2},
        'aliases': [],
        'version': '2.0',
    }


@mark.asyncio
@mark.parametrize('version', ['1.1', '2.0'])
async def test_declare_vbump(app_client, version):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True, 'ctr': 1, 'dummy': 2},
        'version': '1.0',
    }))
    res.raise_for_status()
    assert res.json() == {'outcome': 'created', }

    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True, 'ctr': 1, 'dummy': 2},
        'version': version,
    }))
    res.raise_for_status()
    assert res.json() == {
        'outcome': 'upgraded',
        'previous_version': '1.0',
        'differences': [],
    }

    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True, 'ctr': 1, 'dummy': 2},
        'aliases': [],
        'version': version,
    }


@mark.asyncio
async def test_declare_same_as_alias(app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True, 'ctr': 1, 'dummy': 2},
        'version': '1.0',
    }))
    res.raise_for_status()
    assert res.json() == {'outcome': 'created', }

    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 300,
        'metadata': {'testing': True, 'ctr': 2},
        'alias': 'size_limit',
        'version': '2.0',
    }))
    assert res.status_code == 422


@mark.asyncio
async def test_declare_nonexistant_alias(app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True, 'ctr': 1, 'dummy': 2},
        'version': '1.0',
    }))
    res.raise_for_status()
    assert res.json() == {'outcome': 'created', }

    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 300,
        'metadata': {'testing': True, 'ctr': 2},
        'alias': 'foobar',
        'version': '2.0',
    }))
    assert res.status_code == 404


@mark.asyncio
async def test_declare_conflict(size_limit_setting, app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'str',
        'default_value': "200",
        'metadata': {'testing': True}
    }))
    assert res.status_code == 409


@mark.asyncio
async def test_modify_with_fcs_in_use_safe(size_limit_setting, app_client):
    (await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {'user': '1'},
        'value': 10,
    }))).raise_for_status()

    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'version': '1.1',
    }))
    assert res.json() == {
        'outcome': 'upgraded',
        'previous_version': '1.0',
        'differences': [
            {'level': 'minor', 'message': "removal of configurable features ['theme']"}
        ]
    }


@mark.asyncio
async def test_modify_with_fcs_in_use(size_limit_setting, app_client):
    (await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {'user': '1', 'theme': '2'},
        'value': 10,
    }))).raise_for_status()

    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'version': '2.0',
    }))
    assert res.status_code == 409
    assert res.json()['differences'] == [
        {'level': 'mismatch', 'message': "configurable features ['theme'] are still in use by rules [1]"}
    ]


@mark.asyncio
async def test_declare_major_changes_on_minor_vbump(size_limit_setting, app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme', 'trust'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'version': '1.1',
    }))
    assert res.status_code == 409


@mark.asyncio
async def test_declare_major_changes_on_major_vbump(size_limit_setting, app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme', 'trust'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'version': '2.0',
    }))
    res.raise_for_status()
    assert res.json() == {
        'outcome': 'upgraded',
        'previous_version': '1.0',
        'differences': [
            {'level': 'major', 'attribute': "configurable_features", 'latest_value': ['user', 'theme']}
        ]
    }

    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'trust', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'aliases': [],
        'version': '2.0',
    }


@mark.asyncio
async def test_declare_type_upgrade(size_limit_setting, app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'float',
        'default_value': 200,
        'metadata': {'testing': True},
        'version': '2.0',
    }))
    res.raise_for_status()
    assert res.json() == {
        'outcome': 'upgraded',
        'previous_version': '1.0',
        'differences': [{'level': 'major', 'attribute': 'type', 'latest_value': 'int'}]
    }

    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'float',
        'default_value': 200,
        'metadata': {'testing': True},
        'aliases': [],
        'version': '2.0',
    }

    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'version': '1.0',
    }))
    assert res.json() == {
        'outcome': 'outdated',
        'latest_version': '2.0',
        'differences': [{'level': 'major', 'attribute': 'type', 'latest_value': 'float'}]
    }


@mark.asyncio
async def test_declare_type_upgrade_to_subtype(app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'color',
        'configurable_features': ['user', 'theme'],
        'type': 'Enum[0,1,2]',
        'default_value': 1,
        'metadata': {'testing': True},
        'version': '1.0',
    }))
    res.raise_for_status()
    assert res.json() == {
        'outcome': 'created',
    }

    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'color',
        'configurable_features': ['user', 'theme'],
        'type': 'Enum[0,1]',
        'default_value': 1,
        'metadata': {'testing': True},
        'version': '1.1',
    }))
    res.raise_for_status()
    assert res.json() == {
        'outcome': 'upgraded',
        'previous_version': '1.0',
        'differences': [{'level': 'minor', 'attribute': 'type', 'latest_value': 'Enum[0,1,2]'}]
    }

    res = await app_client.get('/api/v1/settings/color')
    res.raise_for_status()
    assert res.json() == {
        'name': 'color',
        'configurable_features': ['user', 'theme'],
        'type': 'Enum[0,1]',
        'default_value': 1,
        'metadata': {'testing': True},
        'aliases': [],
        'version': '1.1',
    }

    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'color',
        'configurable_features': ['user', 'theme'],
        'type': 'Enum[0,1,2]',
        'default_value': 1,
        'metadata': {'testing': True},
        'version': '1.0',
    }))
    assert res.json() == {
        'outcome': 'outdated',
        'latest_version': '1.1',
        'differences': [{'level': 'minor', 'attribute': 'type', 'latest_value': 'Enum[0,1]'}]
    }


@mark.asyncio
async def test_modify_type_incompatible(size_limit_setting, app_client):
    (await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {'user': '1', 'theme': '2'},
        'value': 10,
    }))).raise_for_status()

    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user'],
        'type': 'Enum[0,11,12]',
        'default_value': 0,
        'metadata': {'testing': True},
        'version': '2.0',
    }))
    assert res.status_code == 409
    assert {'level': 'mismatch', 'message': 'setting type incompatible with values for rules: [1]'} \
           in res.json()['differences']


@mark.asyncio
async def test_declare_multiversion(size_limit_setting, app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'foo',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'alias': 'size_limit',
        'version': '2.0',
    }))
    res.raise_for_status()
    assert res.json()['outcome'] == 'upgraded'
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'version': '1.0',
    }))
    res.raise_for_status()
    assert res.json()['outcome'] == 'outdated'

    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'bar',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'alias': 'foo',
        'version': '3.0',
    }))
    res.raise_for_status()
    assert res.json()['outcome'] == 'upgraded'

    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'version': '1.0',
    }))
    res.raise_for_status()
    assert res.json()['outcome'] == 'outdated'
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'foo',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'alias': 'size_limit',
        'version': '2.0',
    }))
    res.raise_for_status()
    assert res.json()['outcome'] == 'outdated'
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'bar',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'alias': 'foo',
        'version': '3.0',
    }))
    res.raise_for_status()
    assert res.json()['outcome'] == 'uptodate'


@mark.asyncio
async def test_declare_incomplete(size_limit_setting, app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'version': '0.1',
    }))
    res.raise_for_status()
    assert res.json() == {
        'outcome': 'outdated',
        'latest_version': '1.0',
        'differences': [{'level': 'major', 'attribute': 'configurable_features', 'latest_value': ['user', 'theme']}]
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
        'version': '1.0',
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
        'version': '1.0',
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
        res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
            'name': name,
            'configurable_features': ['user'],
            'type': 'int',
            'default_value': 200,
        }))
        res.raise_for_status()
        assert res.json() == {
            'outcome': 'created',
        }

    await mk_setting('a')
    await mk_setting('c')
    await mk_setting('b')

    request_data = {}
    if additional_data is not None:
        request_data['include_additional_data'] = additional_data

    res = await app_client.get('/api/v1/settings', query_string=request_data)
    res.raise_for_status()
    assert res.json() == {
        'settings': [
            {'name': 'a', 'type': 'int', 'default_value': 200, 'version': '1.0'},
            {'name': 'b', 'type': 'int', 'default_value': 200, 'version': '1.0'},
            {'name': 'c', 'type': 'int', 'default_value': 200, 'version': '1.0'},
        ]
    }


@mark.asyncio
async def test_get_settings_additional_data(app_client):
    async def mk_setting(name: str, type: str, default):
        res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
            'name': name,
            'configurable_features': ['theme', 'user'],
            'type': type,
            'default_value': default,
        }))
        res.raise_for_status()
        assert res.json() == {
            'outcome': 'created',
        }

    await mk_setting('a', 'int', 200)
    await mk_setting('c', 'float', 200.0)
    await mk_setting('b', 'str', '200')

    res = await app_client.get('/api/v1/settings', query_string={
        'include_additional_data': True
    })
    res.raise_for_status()
    assert res.json() == {
        'settings': [
            {'name': 'a', 'type': 'int', 'configurable_features': ['user', 'theme'],
             'metadata': {}, 'default_value': 200, 'aliases': [], 'version': '1.0'},
            {'name': 'b', 'type': 'str', 'configurable_features': ['user', 'theme'],
             'metadata': {}, 'default_value': '200', 'aliases': [], 'version': '1.0'},
            {'name': 'c', 'type': 'float', 'configurable_features': ['user', 'theme'],
             'metadata': {}, 'default_value': 200.0, 'aliases': [], 'version': '1.0'},
        ]
    }


@fixture
async def interval_setting(app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'interval',
        'configurable_features': ['user', 'theme'],
        'type': 'float',
        'default_value': 5,
        'metadata': {'testing': True}
    }))
    res.raise_for_status()
    assert res.json() == {
        'outcome': 'created',
    }


@mark.asyncio
@mark.parametrize('new_type', ['float', 'int'])
async def test_type_downgrade_no_rules(interval_setting, app_client, new_type):
    res = await app_client.put('/api/v1/settings/interval/type', json={
        'type': new_type,
        'version': '2.0',
    })
    assert res.status_code == 204
    assert not res.content

    res = await app_client.get('/api/v1/settings/interval')
    res.raise_for_status()
    resp_json = res.json()
    assert resp_json['type'] == new_type
    assert resp_json['default_value'] == 5
    assert resp_json['version'] == '2.0'


@mark.asyncio
async def test_type_downgrade_no_rules_default_conflict(interval_setting, app_client):
    res = await app_client.put('/api/v1/settings/interval/type', json={
        'type': 'bool',
        'version': '2.0',
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
        'type': 'int',
        'version': '2.0',
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
        'type': 'int',
        'version': '2.0',
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
        'type': new_type,
        'version': '2.0',
    })
    assert res.status_code == 404


@mark.asyncio
async def test_type_downgrade_with_rules_enum(app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'background_color',
        'configurable_features': ['theme'],
        'type': 'Enum["red", "blue", "green"]',
        'default_value': "blue",
        'metadata': {'testing': True}
    }))
    res.raise_for_status()
    assert res.json() == {
        'outcome': 'created',
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
        'type': 'Enum["blue", "green", "yellow"]',
        'version': '2.0',
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
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'background_color',
        'configurable_features': ['theme'],
        'type': 'Enum["red", "blue", "green"]',
        'default_value': "blue",
        'metadata': {'testing': True}
    }))
    res.raise_for_status()
    assert res.json() == {
        'outcome': 'created',
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
        'type': 'Enum["blue", "green", "yellow"]',
        'version': '2.0',
    })
    assert res.status_code == 409

    res = await app_client.get('/api/v1/settings/background_color')
    res.raise_for_status()
    resp_json = res.json()
    assert resp_json['type'] == 'Enum["blue","green","red"]'
    assert resp_json['default_value'] == "blue"


@mark.asyncio
@mark.parametrize('old', ['A1', 'A'])
async def test_rename_setting(app_client, old):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'A1',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
    }))
    res.raise_for_status()
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'A',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'alias': 'A1',
        'version': '2.0',
    }))
    res.raise_for_status()
    res = await app_client.put(f'/api/v1/settings/{old}/name', data=json.dumps({'name': 'Z', 'version': '2.1'}))
    res.raise_for_status()
    res = await app_client.get('/api/v1/settings/Z')
    res.raise_for_status()
    data = res.json()
    assert data['name'] == 'Z'
    assert set(data['aliases']) == {'A', 'A1'}
    assert data['version'] == '2.1'


@mark.asyncio
@mark.parametrize('old', ['A', 'A1'])
async def test_rename_setting_no_action_needed(app_client, old):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'A1',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
    }))
    res.raise_for_status()
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'A',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'alias': 'A1',
        'version': '2.0',
    }))
    res.raise_for_status()
    res = await app_client.put(f'/api/v1/settings/{old}/name', data=json.dumps({'name': 'A', 'version': '2.1'}))
    res.raise_for_status()
    res = await app_client.get('/api/v1/settings/A')
    res.raise_for_status()
    data = res.json()
    assert data['name'] == 'A'
    assert set(data['aliases']) == {'A1'}
    assert data['version'] == '2.1'


@mark.asyncio
@mark.parametrize('old', ['A', 'A1', ])
async def test_rename_setting_to_alias(app_client, old):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'A1',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
    }))
    res.raise_for_status()
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'A',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'alias': 'A1',
        'version': '2.0',
    }))
    res.raise_for_status()
    res = await app_client.put(f'/api/v1/settings/{old}/name', data=json.dumps({'name': 'A1', 'version': '2.1'}))
    res.raise_for_status()
    res = await app_client.get('/api/v1/settings/A1')
    res.raise_for_status()
    data = res.json()
    assert data['name'] == 'A1'
    assert set(data['aliases']) == {'A'}
    assert data['version'] == '2.1'


@mark.asyncio
async def test_rename_setting_to_alias_with_declaration(app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'A1',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
    }))
    res.raise_for_status()
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'A',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'alias': 'A1',
        'version': '2.0',
    }))
    res.raise_for_status()
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'A1',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'alias': 'A',
        'version': '2.1',
    }))
    res.raise_for_status()
    res = await app_client.get('/api/v1/settings/A1')
    res.raise_for_status()
    data = res.json()
    assert data['name'] == 'A1'
    assert set(data['aliases']) == {'A'}
    assert data['version'] == '2.1'


@mark.asyncio
@mark.parametrize('old,new', [
    ('A', 'B'),
    ('A', 'B1'),
    ('A1', 'B'),
    ('A1', 'B1'),
])
async def test_rename_setting_existing(app_client, old, new):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'A1',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
    }))
    res.raise_for_status()
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'A',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'alias': 'A1',
        'version': '2.0',
    }))
    res.raise_for_status()
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'B1',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
    }))
    res.raise_for_status()
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'B',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'alias': 'B1',
        'version': '2.0',
    }))
    res.raise_for_status()
    res = await app_client.put(f'/api/v1/settings/{old}/name', data=json.dumps({'name': new, 'version': '2.1'}))
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
    res = await app_client.put('/api/v1/settings/X/name', data=json.dumps({'name': 'Y', 'version': '2.1'}))
    with raises(HTTPError):
        res.raise_for_status()


@mark.asyncio
async def test_rename_setting_cascade(app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
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
    res = await app_client.put('/api/v1/settings/A/name', data=json.dumps({'name': 'Z', 'version': '2.1'}))
    res.raise_for_status()
    res = await app_client.get(f'/api/v1/rules/{rule_id}')
    res.raise_for_status()
    assert res.json()["setting"] == "Z"


@mark.asyncio
async def test_set_cfs_minor(size_limit_setting, app_client):
    res = await app_client.put('/api/v1/settings/size_limit/configurable_features', data=json.dumps({
        'configurable_features': ['user'],
        'version': '1.1'
    }))
    assert res.status_code == 204
    assert not res.content

    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'aliases': [],
        'version': '1.1',
    }


@mark.asyncio
async def test_set_cfs_minor_rejected(size_limit_setting, app_client):
    res = await app_client.put('/api/v1/settings/size_limit/configurable_features', data=json.dumps({
        'configurable_features': ['user', 'theme', 'trust'],
        'version': '1.1'
    }))
    assert res.status_code == 409

    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'aliases': [],
        'version': '1.0',
    }


@mark.asyncio
async def test_set_cfs_minor_conflict(size_limit_setting, app_client):
    (await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {'user': '1', 'theme': '2'},
        'value': 10,
    }))).raise_for_status()

    res = await app_client.put('/api/v1/settings/size_limit/configurable_features', data=json.dumps({
        'configurable_features': ['user'],
        'version': '1.1'
    }))
    assert res.status_code == 409

    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'aliases': [],
        'version': '1.0',
    }


@mark.asyncio
async def test_set_cfs_no_change(size_limit_setting, app_client):
    res = await app_client.put('/api/v1/settings/size_limit/configurable_features', data=json.dumps({
        'configurable_features': ['user', 'theme'],
        'version': '1.1'
    }))
    assert res.status_code == 204
    assert not res.content

    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'aliases': [],
        'version': '1.1',
    }


@mark.asyncio
async def test_set_cfs_outdated(size_limit_setting, app_client):
    res = await app_client.put('/api/v1/settings/size_limit/configurable_features', data=json.dumps({
        'configurable_features': ['user', 'theme'],
        'version': '0.1'
    }))
    assert res.status_code == 409

    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'aliases': [],
        'version': '1.0',
    }


@mark.asyncio
async def test_set_cfs_same(size_limit_setting, app_client):
    res = await app_client.put('/api/v1/settings/size_limit/configurable_features', data=json.dumps({
        'configurable_features': ['user', 'theme'],
        'version': '1.0'
    }))
    assert res.status_code == 204
    assert not res.content

    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True},
        'aliases': [],
        'version': '1.0',
    }


@mark.asyncio
@mark.parametrize('new_type', ['float', 'int'])
async def test_type_change_outdated(interval_setting, app_client, new_type):
    res = await app_client.put('/api/v1/settings/interval/type', json={
        'type': new_type,
        'version': '0.1',
    })
    assert res.status_code == 409

    res = await app_client.get('/api/v1/settings/interval')
    res.raise_for_status()
    resp_json = res.json()
    assert resp_json['type'] == 'float'
    assert resp_json['default_value'] == 5
    assert resp_json['version'] == '1.0'


@mark.asyncio
@mark.parametrize('new_version', ['1.0', '1.1'])
async def test_type_no_change(interval_setting, app_client, new_version):
    res = await app_client.put('/api/v1/settings/interval/type', json={
        'type': 'float',
        'version': new_version,
    })
    assert res.status_code == 204
    assert not res.content

    res = await app_client.get('/api/v1/settings/interval')
    res.raise_for_status()
    resp_json = res.json()
    assert resp_json['type'] == 'float'
    assert resp_json['default_value'] == 5
    assert resp_json['version'] == new_version


@mark.asyncio
async def test_type_major_on_minor(size_limit_setting, app_client):
    res = await app_client.put('/api/v1/settings/size_limit/type', json={
        'type': 'float',
        'version': '1.1',
    })
    assert res.status_code == 409

    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    resp_json = res.json()
    assert resp_json['type'] == 'int'
    assert resp_json['default_value'] == 200
    assert resp_json['version'] == '1.0'


@mark.asyncio
async def test_type_outdated(size_limit_setting, app_client):
    res = await app_client.put('/api/v1/settings/size_limit/type', json={
        'type': 'float',
        'version': '0.1',
    })
    assert res.status_code == 409

    res = await app_client.get('/api/v1/settings/size_limit')
    res.raise_for_status()
    resp_json = res.json()
    assert resp_json['type'] == 'int'
    assert resp_json['default_value'] == 200
    assert resp_json['version'] == '1.0'


@mark.asyncio
@mark.parametrize('new_version', ['1.0', '1.1'])
async def test_rename_no_change(interval_setting, app_client, new_version):
    res = await app_client.put('/api/v1/settings/interval/name', json={
        'name': 'interval',
        'version': new_version,
    })
    assert res.status_code == 204
    assert not res.content

    res = await app_client.get('/api/v1/settings/interval')
    res.raise_for_status()
    resp_json = res.json()
    assert resp_json['type'] == 'float'
    assert resp_json['default_value'] == 5
    assert resp_json['version'] == new_version


@mark.asyncio
@mark.parametrize('new_name', ['interval', 'fooobar'])
async def test_rename_outdated(interval_setting, app_client, new_name):
    res = await app_client.put('/api/v1/settings/interval/name', json={
        'name': new_name,
        'version': '0.1',
    })
    assert res.status_code == 409

    res = await app_client.get('/api/v1/settings/interval')
    res.raise_for_status()
    resp_json = res.json()
    assert resp_json['type'] == 'float'
    assert resp_json['default_value'] == 5
    assert resp_json['version'] == '1.0'


@mark.asyncio
@mark.parametrize('new_name', ['interval', 'fooobar'])
async def test_rename_back(interval_setting, app_client, new_name):
    res = await app_client.put('/api/v1/settings/interval/name', json={
        'name': new_name,
        'version': '0.1',
    })
    assert res.status_code == 409

    res = await app_client.get('/api/v1/settings/interval')
    res.raise_for_status()
    resp_json = res.json()
    assert resp_json['type'] == 'float'
    assert resp_json['default_value'] == 5
    assert resp_json['version'] == '1.0'
