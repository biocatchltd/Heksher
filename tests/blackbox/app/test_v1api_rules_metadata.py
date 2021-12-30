import json

from pytest import mark


@mark.asyncio
async def test_post_rule_metadata(example_rule, app_client):
    res = await app_client.post(f'/api/v1/rules/{example_rule}/metadata', data=json.dumps({
        'metadata': {'test': False, 'second_key': 12}
    }))
    res.raise_for_status()
    rule = await app_client.get(f'/api/v1/rules/{example_rule}')
    rule.raise_for_status()
    assert rule.json() == {
        'setting': 'size_limit',
        'value': 10,
        'feature_values': [['theme', 'bright']],
        'metadata': {'test': False, 'second_key': 12}
    }


@mark.asyncio
async def test_post_rule_metadata_new_key(example_rule, app_client):
    res = await app_client.post(f'/api/v1/rules/{example_rule}/metadata', data=json.dumps({
        'metadata': {'second_key': 12}
    }))
    res.raise_for_status()
    rule = await app_client.get(f'/api/v1/rules/{example_rule}')
    rule.raise_for_status()
    assert rule.json() == {
        'setting': 'size_limit',
        'value': 10,
        'feature_values': [['theme', 'bright']],
        'metadata': {'test': True, 'second_key': 12}
    }


@mark.asyncio
async def test_post_not_existing_rule_metadata(app_client):
    res = await app_client.post('/api/v1/rules/1234/metadata', data=json.dumps({
        'metadata': {'test': True}
    }))
    assert res.status_code == 404


@mark.asyncio
async def test_post_rule_first_metadata(example_rule, app_client):
    await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'test_setting',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 0,
        'metadata': {}
    }))

    post_rule_rep = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'test_setting',
        'feature_values': {'theme': 'bright'},
        'value': 0,
        'metadata': {}
    }))
    post_rule_rep.raise_for_status()
    j_result = post_rule_rep.json()
    rule_id = j_result.pop('rule_id')

    res = await app_client.post(f'/api/v1/rules/{rule_id}/metadata', data=json.dumps({
        'metadata': {'test': True}
    }))
    res.raise_for_status()
    rule = await app_client.get(f'/api/v1/rules/{rule_id}')
    assert rule.json() == {
        'setting': 'test_setting',
        'value': 0,
        'feature_values': [['theme', 'bright']],
        'metadata': {'test': True}
    }


@mark.asyncio
async def test_put_rule_metadata(example_rule, app_client):
    res = await app_client.put(f'/api/v1/rules/{example_rule}/metadata', data=json.dumps({
        'metadata': {'first': 'yes', 'second': 'no'}
    }))
    res.raise_for_status()
    rule = await app_client.get(f'/api/v1/rules/{example_rule}')
    rule.raise_for_status()
    assert rule.json() == {
        'setting': 'size_limit',
        'value': 10,
        'feature_values': [['theme', 'bright']],
        'metadata': {'first': 'yes', 'second': 'no'}
    }


@mark.asyncio
async def test_put_not_existing_rule_metadata(app_client):
    res = await app_client.put('/api/v1/rules/12345/metadata', data=json.dumps({
        'metadata': {'test': True}
    }))
    assert res.status_code == 404


@mark.asyncio
async def test_put_rule_empty_metadata(example_rule, app_client):
    res = await app_client.put(f'/api/v1/rules/{example_rule}/metadata', data=json.dumps({
        'metadata': {}
    }))
    res.raise_for_status()
    rule = await app_client.get(f'/api/v1/rules/{example_rule}')
    rule.raise_for_status()
    assert rule.json() == {
        'setting': 'size_limit',
        'value': 10,
        'feature_values': [['theme', 'bright']],
        'metadata': {}
    }


@mark.asyncio
async def test_put_rule_metadata_existing_key(example_rule, app_client):
    res = await app_client.put(f'/api/v1/rules/{example_rule}/metadata/test', data=json.dumps({
        'value': 1000
    }))
    res.raise_for_status()
    rule = await app_client.get(f'/api/v1/rules/{example_rule}')
    rule.raise_for_status()
    assert rule.json() == {
        'setting': 'size_limit',
        'value': 10,
        'feature_values': [['theme', 'bright']],
        'metadata': {'test': 1000}
    }


@mark.asyncio
async def test_put_rule_metadata_not_existing_key(example_rule, app_client):
    res = await app_client.put(f'/api/v1/rules/{example_rule}/metadata/hello', data=json.dumps({
        'value': 'world'
    }))
    res.raise_for_status()
    rule = await app_client.get(f'/api/v1/rules/{example_rule}')
    rule.raise_for_status()
    assert rule.json() == {
        'setting': 'size_limit',
        'value': 10,
        'feature_values': [['theme', 'bright']],
        'metadata': {'test': True, 'hello': 'world'}
    }


@mark.asyncio
async def test_delete_rule_metadata(example_rule, app_client):
    res = await app_client.delete(f'/api/v1/rules/{example_rule}/metadata')
    res.raise_for_status()
    rule = await app_client.get(f'/api/v1/rules/{example_rule}')
    rule.raise_for_status()
    assert rule.json() == {
        'setting': 'size_limit',
        'value': 10,
        'feature_values': [['theme', 'bright']],
        'metadata': {}
    }


@mark.asyncio
async def test_delete_not_existing_rule_metadata(app_client):
    res = await app_client.delete('/api/v1/rules/1234/metadata')
    assert res.status_code == 404


@mark.asyncio
async def test_delete_specific_key_from_rule_metadata(example_rule, app_client):
    await app_client.put(f'/api/v1/rules/{example_rule}/metadata/hello', data=json.dumps({
        'value': 'world'
    }))
    res = await app_client.delete(f'/api/v1/rules/{example_rule}/metadata/test')
    res.raise_for_status()
    rule = await app_client.get(f'/api/v1/rules/{example_rule}')
    rule.raise_for_status()
    assert rule.json() == {
        'setting': 'size_limit',
        'value': 10,
        'feature_values': [['theme', 'bright']],
        'metadata': {'hello': 'world'}
    }


@mark.asyncio
async def test_get_rule_metadata(example_rule, app_client):
    res = await app_client.get(f'/api/v1/rules/{example_rule}/metadata')
    res.raise_for_status()
    assert res.json() == {
        'metadata': {'test': True}
    }


@mark.asyncio
async def test_get_rule_no_metadata(app_client):
    await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'test_setting',
        'configurable_features': ['theme', 'user'],
        'type': 'int'
    }))

    post_rule_rep = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'test_setting',
        'feature_values': {'theme': 'bright'},
        'value': 0,
        'metadata': {}
    }))
    post_rule_rep.raise_for_status()
    j_result = post_rule_rep.json()
    rule_id = j_result.pop('rule_id')

    res = await app_client.get(f'/api/v1/rules/{rule_id}/metadata')
    res.raise_for_status()
    assert res.json() == {
        'metadata': {}
    }
