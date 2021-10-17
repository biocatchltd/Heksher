import json

from pytest import mark


@mark.asyncio
async def test_post_setting_metadata(size_limit_setting, app_client):
    res = await app_client.post('/api/v1/settings/size_limit/metadata', data=json.dumps({
        'metadata': {'testing': False, 'second_key': 12}
    }))
    res.raise_for_status()
    setting = await app_client.get('/api/v1/settings/size_limit')
    assert setting.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': False, 'second_key': 12}
    }


@mark.asyncio
async def test_post_setting_metadata_new_key(size_limit_setting, app_client):
    res = await app_client.post('/api/v1/settings/size_limit/metadata', data=json.dumps({
        'metadata': {'second_key': 12}
    }))
    res.raise_for_status()
    setting = await app_client.get('/api/v1/settings/size_limit')
    assert setting.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True, 'second_key': 12}
    }


@mark.asyncio
async def test_post_not_existing_setting_metadata(app_client):
    res = await app_client.post('/api/v1/settings/no_setting/metadata', data=json.dumps({
        'metadata': {'testing': True}
    }))
    assert res.status_code == 404


@mark.asyncio
async def test_post_setting_first_metadata(app_client):
    await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'test_setting',
        'configurable_features': ['user'],
        'type': 'int',
        'default_value': 10,
        'metadata': {}
    }))
    res = await app_client.post('/api/v1/settings/test_setting/metadata', data=json.dumps({
        'metadata': {'testing': True}
    }))
    res.raise_for_status()
    setting = await app_client.get('/api/v1/settings/test_setting')
    assert setting.json() == {
        'name': 'test_setting',
        'configurable_features': ['user'],
        'type': 'int',
        'default_value': 10,
        'metadata': {'testing': True}
    }


@mark.asyncio
async def test_put_setting_metadata(size_limit_setting, app_client):
    res = await app_client.put('/api/v1/settings/size_limit/metadata', data=json.dumps({
        'metadata': {'first': 'yes', 'second': 'no'}
    }))
    res.raise_for_status()
    setting = await app_client.get('/api/v1/settings/size_limit')
    assert setting.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'first': 'yes', 'second': 'no'}
    }


@mark.asyncio
async def test_put_not_existing_setting_metadata(app_client):
    res = await app_client.put('/api/v1/settings/no_setting/metadata', data=json.dumps({
        'metadata': {'testing': True}
    }))
    assert res.status_code == 404


@mark.asyncio
async def test_put_setting_empty_metadata(size_limit_setting, app_client):
    res = await app_client.put('/api/v1/settings/size_limit/metadata', data=json.dumps({
        'metadata': {}
    }))
    res.raise_for_status()
    setting = await app_client.get('/api/v1/settings/size_limit')
    assert setting.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {}
    }


@mark.asyncio
async def test_put_setting_metadata_existing_key(size_limit_setting, app_client):
    res = await app_client.put('/api/v1/settings/size_limit/metadata/testing', data=json.dumps({
        'value': 1000
    }))
    res.raise_for_status()
    setting = await app_client.get('/api/v1/settings/size_limit')
    assert setting.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': 1000}
    }


@mark.asyncio
async def test_put_setting_metadata_not_existing_key(size_limit_setting, app_client):
    res = await app_client.put('/api/v1/settings/size_limit/metadata/hello', data=json.dumps({
        'value': 'world'
    }))
    res.raise_for_status()
    setting = await app_client.get('/api/v1/settings/size_limit')
    assert setting.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True, 'hello': 'world'}
    }


@mark.asyncio
async def test_delete_setting_metadata(size_limit_setting, app_client):
    res = await app_client.delete('/api/v1/settings/size_limit/metadata')
    res.raise_for_status()
    setting = await app_client.get('/api/v1/settings/size_limit')
    assert setting.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {}
    }


@mark.asyncio
async def test_delete_not_existing_setting_metadata(app_client):
    res = await app_client.delete('/api/v1/settings/test_setting/metadata')
    assert res.status_code == 404


@mark.asyncio
async def test_delete_specific_key_from_setting_metadata(size_limit_setting, app_client):
    await app_client.put('/api/v1/settings/size_limit/metadata/hello', data=json.dumps({
        'value': 'world'
    }))
    res = await app_client.delete('/api/v1/settings/size_limit/metadata/testing')
    res.raise_for_status()
    setting = await app_client.get('/api/v1/settings/size_limit')
    assert setting.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'hello': 'world'}
    }


@mark.asyncio
async def test_get_setting_metadata(size_limit_setting, app_client):
    res = await app_client.get('/api/v1/settings/size_limit/metadata')
    res.raise_for_status()
    assert res.json() == {
        'metadata': {'testing': True}
    }


@mark.asyncio
async def test_get_setting_no_metadata(app_client):
    await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'test_setting',
        'configurable_features': ['user'],
        'type': 'int',
        'default_value': 10,
        'metadata': {}
    }))
    res = await app_client.get('/api/v1/settings/test_setting/metadata')
    res.raise_for_status()
    assert res.json() == {
        'metadata': {}
    }
