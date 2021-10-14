import json
from datetime import datetime, timedelta
from itertools import chain

from pytest import fixture, mark


@fixture
async def example_rule(size_limit_setting, app_client):
    res = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {'theme': 'bright'},
        'value': 10,
        'metadata': {'test': True}
    }))
    res.raise_for_status()
    j_result = res.json()
    rule_id = j_result.pop('rule_id')
    assert not j_result

    return rule_id


@mark.asyncio
async def test_add_rule(example_rule, app_client):
    res = await app_client.get(f'/api/v1/rules/{example_rule}')
    res.raise_for_status()
    assert res.json() == {
        'setting': 'size_limit',
        'value': 10,
        'feature_values': [['theme', 'bright']],
        'metadata': {'test': True}
    }


@mark.asyncio
async def test_add_rule_no_conds(size_limit_setting, app_client):
    res = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {},
        'value': 10,
        'metadata': {'test': True}
    }))
    assert res.status_code == 422


@mark.asyncio
async def test_add_rule_missing_setting(app_client):
    res = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit_2',
        'feature_values': {'theme': 'bright'},
        'value': 10,
        'metadata': {'test': True}
    }))
    assert 400 <= res.status_code <= 499


@mark.asyncio
async def test_add_rule_non_configurable(size_limit_setting, app_client):
    res = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {'trust': 'full'},
        'value': 10,
        'metadata': {'test': True}
    }))
    assert 400 <= res.status_code <= 499


@mark.asyncio
async def test_add_rule_bad_type(size_limit_setting, app_client):
    res = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {'theme': 'bright'},
        'value': True,
        'metadata': {'test': True}
    }))
    assert 400 <= res.status_code <= 499


@mark.asyncio
async def test_add_rule_existing(example_rule, app_client):
    res = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {'theme': 'bright'},
        'value': 10,
        'metadata': {'test': True}
    }))
    assert res.status_code == 409


@mark.asyncio
async def test_block_injection(example_rule, app_client):
    res = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {'theme': "' OR 1='1"},
        'value': 10,
        'metadata': {'test': True}
    }))
    assert res.status_code == 422


@mark.asyncio
async def test_delete_rule(example_rule, app_client):
    res = await app_client.delete(f'/api/v1/rules/{example_rule}')
    res.raise_for_status()
    assert not res.content
    res = await app_client.get(f'/api/v1/rules/{example_rule}')
    assert res.status_code == 404


@mark.asyncio
async def test_delete_rule_missing(example_rule, app_client):
    res = await app_client.delete(f'/api/v1/rules/{example_rule + 1}')
    assert res.status_code == 404


@mark.asyncio
async def test_get_rule_missing(example_rule, app_client):
    res = await app_client.get(f'/api/v1/rules/{example_rule + 1}')
    assert res.status_code == 404


@mark.asyncio
async def test_search_rule(example_rule, app_client, sql_service):
    res = await app_client.post('/api/v1/rules/search', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': [('theme', 'bright')]
    }))
    res.raise_for_status()
    assert res.json() == {
        'rule_id': example_rule
    }


@mark.asyncio
async def test_search_rule_empty(example_rule, app_client, sql_service):
    res = await app_client.get('/api/v1/rules/search', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': []
    }))
    assert res.status_code == 422


@mark.asyncio
async def test_search_rule_missing(example_rule, app_client):
    res = await app_client.post('/api/v1/rules/search', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': [('theme', 'dark')]
    }))
    assert res.status_code == 404


@fixture
def mk_setting(app_client):
    async def mk_setting(name: str):
        res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
            'name': name,
            'configurable_features': ['theme', 'trust', 'user'],
            'type': 'int'
        }))
        res.raise_for_status()
        assert res.json() == {
            'created': True,
            'changed': [],
            'incomplete': {}
        }

    return mk_setting


@fixture
def mk_rule(app_client):
    async def mk_rule(setting_name, features, val):
        res = await app_client.post('/api/v1/rules', data=json.dumps({
            'setting': setting_name,
            'feature_values': features,
            'value': val,
            'metadata': {'test': 'yes'}
        }))
        res.raise_for_status()
        assert res.json().keys() == {'rule_id'}

    return mk_rule


@fixture
async def setup_rules(mk_setting, mk_rule):
    await mk_setting('a')
    await mk_setting('b')
    await mk_setting('c')

    await mk_rule('a', {'trust': 'full'}, 1)
    await mk_rule('a', {'theme': 'black'}, 2)
    await mk_rule('a', {'theme': 'black', 'trust': 'full'}, 3)
    await mk_rule('b', {'trust': 'none'}, 4)
    await mk_rule('b', {'trust': 'part'}, 5)
    await mk_rule('c', {'trust': 'full'}, 6)
    await mk_rule('a', {'theme': 'black', 'user': 'admin'}, 7)


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules(metadata: bool, app_client, setup_rules):
    res = await app_client.post('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {'trust': ['full', 'part'], 'theme': ['black']},
        'include_metadata': metadata
    }))

    expected = {
        'rules': {
            'a': [
                {'context_features': [['trust', 'full']], 'value': 1, 'rule_id': 1},
                {'context_features': [['theme', 'black']], 'value': 2, 'rule_id': 2},
                {'context_features': [['trust', 'full'], ['theme', 'black']], 'value': 3, 'rule_id': 3}
            ],
            'b': [
                {'context_features': [['trust', 'part']], 'value': 5, 'rule_id': 5}
            ]
        }
    }
    if metadata:
        for rule in chain.from_iterable(expected['rules'].values()):
            rule['metadata'] = {'test': 'yes'}

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_time_cache(metadata: bool, app_client, setup_rules, mk_rule):
    current_time = datetime.utcnow()
    # touch a to change its last_touch_time
    await mk_rule('a', {'theme': 'grey', 'user': 'admin'}, 8)

    res = await app_client.post('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {'trust': ['full', 'part'], 'theme': ['black']},
        'include_metadata': metadata,
        'cache_time': current_time.isoformat(),
    }))

    expected = {
        'rules': {
            'a': [
                {'context_features': [['trust', 'full']], 'value': 1, 'rule_id': 1},
                {'context_features': [['theme', 'black']], 'value': 2, 'rule_id': 2},
                {'context_features': [['trust', 'full'], ['theme', 'black']], 'value': 3, 'rule_id': 3}
            ],
        }
    }
    if metadata:
        for rule in chain.from_iterable(expected['rules'].values()):
            rule['metadata'] = {'test': 'yes'}

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
@mark.parametrize('suffix', ['Z', '+00:00', '+01:02', '-06:05'])
async def test_query_rules_bad_cache_time_zone(metadata: bool, suffix: str, app_client, setup_rules, mk_rule):
    current_time = datetime.utcnow()
    # touch a to change its last_touch_time
    await mk_rule('a', {'theme': 'grey', 'user': 'admin'}, 8)

    res = await app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {'trust': ['full', 'part'], 'theme': ['black']},
        'include_metadata': metadata,
        'cache_time': current_time.isoformat() + suffix,
    }))
    assert res.status_code == 422


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_fully_cached(metadata: bool, app_client, setup_rules, mk_rule):
    current_time = datetime.utcnow()

    res = await app_client.post('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {'trust': ['full', 'part'], 'theme': ['black']},
        'include_metadata': metadata,
        'cache_time': current_time.isoformat(),
    }))

    expected = {
        'rules': {}
    }

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_with_empty(metadata: bool, app_client, setup_rules, sql_service):
    with sql_service.connection() as connection:
        connection.execute("""
        INSERT INTO rules (setting, value) VALUES ('b', '10')
        """)
        connection.execute("""
        INSERT INTO rule_metadata (rule, key, value) VALUES (8, 'test', '"yes"')
        """)

    res = await app_client.post('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {'trust': ['full', 'part'], 'theme': ['black']},
        'include_metadata': metadata
    }))

    expected = {
        'rules': {
            'a': [
                {'context_features': [['trust', 'full']], 'rule_id': 1, 'value': 1},
                {'context_features': [['theme', 'black']], 'rule_id': 2, 'value': 2},
                {'context_features': [['trust', 'full'], ['theme', 'black']], 'rule_id': 3, 'value': 3}
            ],
            'b': [
                {'context_features': [['trust', 'part']], 'rule_id': 5, 'value': 5},
                {'context_features': [], 'rule_id': 8, 'value': 10}
            ]
        }
    }
    if metadata:
        for rule in chain.from_iterable(expected['rules'].values()):
            rule['metadata'] = {'test': 'yes'}

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_nooptions(metadata: bool, app_client, setup_rules):
    res = await app_client.post('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a'],
        'context_features_options': {},
        'include_metadata': metadata
    }))

    expected = {
        'rules': {
            'a': []
        }
    }

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_nooptions_with_matchall(metadata: bool, app_client, setup_rules, sql_service):
    with sql_service.connection() as connection:
        connection.execute("""
        INSERT INTO rules (setting, value) VALUES ('b', '10')
        """)
        connection.execute("""
        INSERT INTO rule_metadata (rule, key, value) VALUES (8, 'test', '"yes"')
        """)

    res = await app_client.post('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {},
        'include_metadata': metadata
    }))

    expected = {
        'rules': {
            'a': [],
            'b': [
                {'context_features': [], 'value': 10, 'rule_id': 8},
            ]
        }
    }

    if metadata:
        for rule in chain.from_iterable(expected['rules'].values()):
            rule['metadata'] = {'test': 'yes'}

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_matchall(metadata: bool, app_client, setup_rules):
    res = await app_client.post('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': '*',
        'include_metadata': metadata
    }))

    expected = {
        'rules': {
            'a': [
                {'context_features': [['trust', 'full']], 'value': 1, 'rule_id': 1},
                {'context_features': [['theme', 'black']], 'value': 2, 'rule_id': 2},
                {'context_features': [['trust', 'full'], ['theme', 'black']], 'rule_id': 3, 'value': 3},
                {'context_features': [['user', 'admin'], ['theme', 'black']], 'rule_id': 7, 'value': 7}
            ],
            'b': [
                {'context_features': [['trust', 'none']], 'rule_id': 4, 'value': 4},
                {'context_features': [['trust', 'part']], 'rule_id': 5, 'value': 5}
            ]
        }
    }
    if metadata:
        for rule in chain.from_iterable(expected['rules'].values()):
            rule['metadata'] = {'test': 'yes'}

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_wildcard_some(metadata: bool, app_client, setup_rules):
    res = await app_client.post('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {'theme': '*', 'trust': ['full', 'none']},
        'include_metadata': metadata
    }))

    expected = {
        'rules': {
            'a': [
                {'context_features': [['trust', 'full']], 'value': 1, 'rule_id': 1},
                {'context_features': [['theme', 'black']], 'value': 2, 'rule_id': 2},
                {'context_features': [['trust', 'full'], ['theme', 'black']], 'value': 3, 'rule_id': 3},
            ],
            'b': [
                {'context_features': [['trust', 'none']], 'value': 4, 'rule_id': 4},
            ]
        }
    }
    if metadata:
        for rule in chain.from_iterable(expected['rules'].values()):
            rule['metadata'] = {'test': 'yes'}

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_wildcard_only(metadata: bool, app_client, setup_rules):
    res = await app_client.post('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {'theme': '*'},
        'include_metadata': metadata
    }))

    expected = {
        'rules': {
            'a': [
                {'context_features': [['theme', 'black']], 'value': 2, 'rule_id': 2},
            ],
            'b': []
        }
    }
    if metadata:
        for rule in chain.from_iterable(expected['rules'].values()):
            rule['metadata'] = {'test': 'yes'}

    assert res.json() == expected


@mark.asyncio
async def test_query_rules_bad_contexts(app_client, setup_rules):
    res = await app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {'trust': ['full', 'part'], 'theme': ['black'], 'love': ['overflowing']},
    }))
    assert 400 <= res.status_code <= 499


@mark.asyncio
async def test_query_rules_empty_contexts(app_client, setup_rules):
    res = await app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {'trust': []}
    }))
    assert 400 <= res.status_code <= 499


@mark.asyncio
async def test_query_rules_bad_settings(app_client, setup_rules):
    res = await app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'd'],
        'context_features_options': {'trust': ['full', 'part'], 'theme': ['black']},
    }))
    assert 400 <= res.status_code <= 499


@mark.asyncio
@mark.parametrize('options', [None, '**', 'wildcard'])
async def test_query_rules_bad_options(app_client, setup_rules, options):
    res = await app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a'],
        'context_features_options': options,
    }))
    assert res.status_code == 422, res.content


@mark.asyncio
@mark.parametrize('options', [None, '**', 'wildcard'])
async def test_query_rules_bad_inner_option(app_client, setup_rules, options):
    res = await app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a'],
        'context_features_options': {'trust': options},
    }))
    assert res.status_code == 422, res.content


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_nosettings(metadata: bool, app_client, setup_rules):
    res = await app_client.post('/api/v1/rules/query', data=json.dumps({
        'setting_names': [],
        'context_features_options': '*',
        'include_metadata': metadata
    }))

    expected = {'rules': {}}

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_bad_cache_future(metadata: bool, app_client, setup_rules, mk_rule):
    future_time = datetime.utcnow() + timedelta(hours=2)
    # touch a to change its last_touch_time
    await mk_rule('a', {'theme': 'grey', 'user': 'admin'}, 8)

    res = await app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {'trust': ['full', 'part'], 'theme': ['black']},
        'include_metadata': metadata,
        'cache_time': future_time.isoformat(),
    }))
    assert res.status_code == 422


@mark.asyncio
async def test_patch_rule_sanity(example_rule, app_client):
    res = await app_client.patch(f'/api/v1/rules/{example_rule}', data=json.dumps(
        {"value": 5}
    ))
    assert res.status_code == 204
    assert not res.content
    res = await app_client.get(f'/api/v1/rules/{example_rule}')
    res.raise_for_status()
    assert res.json() == {
        'setting': 'size_limit',
        'value': 5,
        'feature_values': [['theme', 'bright']],
        'metadata': {'test': True}
    }


@mark.asyncio
async def test_patch_rule_missing(app_client):
    res = await app_client.patch('/api/v1/rules/50000', data=json.dumps(
        {"value": 5}
    ))
    assert res.status_code == 404


@mark.asyncio
async def test_patch_rule_bad_data(example_rule, app_client):
    res = await app_client.patch(f'/api/v1/rules/{example_rule}', data=json.dumps(
        {"value": ["d5"]}
    ))
    assert res.status_code == 400


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
async def test_post_not_existing_rule_metadata(app_client):
    res = await app_client.post('/api/v1/rules/1234/metadata', data=json.dumps({
        'metadata': {'test': True}
    }))
    assert res.status_code == 404


@mark.asyncio
async def test_post_rule_first_metadata(example_rule, app_client):
    await app_client.put('/api/v1/settings/declare', data=json.dumps({
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
async def test_get_rule_metadata(example_rule, app_client):
    res = await app_client.get(f'/api/v1/rules/{example_rule}/metadata')
    res.raise_for_status()
    assert res.json() == {
        'metadata': {'test': True}
    }


@mark.asyncio
async def test_get_rule_no_metadata(app_client):
    await app_client.put('/api/v1/settings/declare', data=json.dumps({
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
