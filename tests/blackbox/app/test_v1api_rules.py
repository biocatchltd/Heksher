import json
from itertools import chain

from pytest import fixture, mark


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
async def test_add_rule_2(example_rule2, app_client):
    res = await app_client.get(f'/api/v1/rules/{example_rule2}')
    res.raise_for_status()
    assert res.json() == {
        'setting': 'size_limit',
        'value': 10,
        'feature_values': [['user', 'me'], ['theme', 'bright']],
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
    res = await app_client.get('/api/v1/rules/search', query_string={
        'setting': 'size_limit',
        'feature_values': 'theme:bright'
    })
    res.raise_for_status()
    assert res.json() == {
        'rule_id': example_rule
    }


@mark.asyncio
async def test_search_rule_empty(example_rule, app_client, sql_service):
    res = await app_client.get('/api/v1/rules/search', query_string={
        'setting': 'size_limit',
        'feature_values': ''
    })
    assert res.status_code == 422


@mark.asyncio
async def test_search_rule_missing(example_rule, app_client):
    res = await app_client.get('/api/v1/rules/search', query_string={
        'setting': 'size_limit',
        'feature_values': 'theme:dark'
    })
    assert res.status_code == 404


@fixture
def mk_setting(app_client):
    async def mk_setting(name: str):
        res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
            'name': name,
            'configurable_features': ['theme', 'trust', 'user'],
            'type': 'int',
            'default_value': 0,
        }))
        res.raise_for_status()
        assert res.json() == {'outcome': 'created'}

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
    await mk_setting('long_setting_name')
    await mk_setting('b')

    await mk_rule('a', {'trust': 'full'}, 1)
    await mk_rule('a', {'theme': 'black'}, 2)
    await mk_rule('a', {'theme': 'black', 'trust': 'full'}, 3)
    await mk_rule('long_setting_name', {'trust': 'none'}, 4)
    await mk_rule('long_setting_name', {'trust': 'part'}, 5)
    await mk_rule('b', {'trust': 'full'}, 6)
    await mk_rule('a', {'theme': 'black', 'user': 'admin'}, 7)


def patch_rule_expectation_with_metadata(expected_rules):
    for rule in chain.from_iterable(s['rules'] for s in expected_rules['settings'].values()):
        rule['metadata'] = {'test': 'yes'}


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules(metadata: bool, app_client, setup_rules):
    res = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a,long_setting_name',
        'context_filters': 'trust:(full,part),theme:(black)',
        'include_metadata': str(metadata)
    })

    expected = {
        'settings': {
            'a': {'rules': [
                {'context_features': [['trust', 'full']], 'value': 1, 'rule_id': 1},
                {'context_features': [['theme', 'black']], 'value': 2, 'rule_id': 2},
                {'context_features': [['trust', 'full'], ['theme', 'black']], 'value': 3, 'rule_id': 3}
            ]},
            'long_setting_name': {'rules': [
                {'context_features': [['trust', 'part']], 'value': 5, 'rule_id': 5}
            ]}
        }
    }
    if metadata:
        patch_rule_expectation_with_metadata(expected)

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_with_empty(metadata: bool, app_client, setup_rules, sql_service):
    with sql_service.connection() as connection:
        connection.execute("""
        INSERT INTO rules (setting, value) VALUES ('long_setting_name', '10')
        """)
        connection.execute("""
        INSERT INTO rule_metadata (rule, key, value) VALUES (8, 'test', '"yes"')
        """)

    res = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a,long_setting_name',
        'context_filters': 'trust:(full,part),theme:(black)',
        'include_metadata': str(metadata)
    })

    expected = {
        'settings': {
            'a': {'rules': [
                {'context_features': [['trust', 'full']], 'rule_id': 1, 'value': 1},
                {'context_features': [['theme', 'black']], 'rule_id': 2, 'value': 2},
                {'context_features': [['trust', 'full'], ['theme', 'black']], 'rule_id': 3, 'value': 3}
            ]},
            'long_setting_name': {'rules': [
                {'context_features': [['trust', 'part']], 'rule_id': 5, 'value': 5},
                {'context_features': [], 'rule_id': 8, 'value': 10}
            ]}
        }
    }
    if metadata:
        patch_rule_expectation_with_metadata(expected)

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_nooptions(metadata: bool, app_client, setup_rules):
    res = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a',
        'context_filters': '',
        'include_metadata': metadata
    })
    res.raise_for_status()

    expected = {
        'settings': {
            'a': {'rules': []}
        }
    }

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_nooptions_with_matchall(metadata: bool, app_client, setup_rules, sql_service):
    with sql_service.connection() as connection:
        connection.execute("""
        INSERT INTO rules (setting, value) VALUES ('long_setting_name', '10')
        """)
        connection.execute("""
        INSERT INTO rule_metadata (rule, key, value) VALUES (8, 'test', '"yes"')
        """)

    res = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a,long_setting_name',
        'context_filters': '',
        'include_metadata': str(metadata)
    })

    expected = {
        'settings': {
            'a': {'rules': []},
            'long_setting_name': {'rules': [
                {'context_features': [], 'value': 10, 'rule_id': 8},
            ]}
        }
    }

    if metadata:
        patch_rule_expectation_with_metadata(expected)

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_matchall(metadata: bool, app_client, setup_rules):
    res = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a,long_setting_name',
        'context_filters': '*',
        'include_metadata': str(metadata)
    })

    expected = {
        'settings': {
            'a': {'rules': [
                {'context_features': [['trust', 'full']], 'value': 1, 'rule_id': 1},
                {'context_features': [['theme', 'black']], 'value': 2, 'rule_id': 2},
                {'context_features': [['trust', 'full'], ['theme', 'black']], 'rule_id': 3, 'value': 3},
                {'context_features': [['user', 'admin'], ['theme', 'black']], 'rule_id': 7, 'value': 7}
            ]},
            'long_setting_name': {'rules': [
                {'context_features': [['trust', 'none']], 'rule_id': 4, 'value': 4},
                {'context_features': [['trust', 'part']], 'rule_id': 5, 'value': 5}
            ]}
        }
    }
    if metadata:
        patch_rule_expectation_with_metadata(expected)

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_wildcard_some(metadata: bool, app_client, setup_rules):
    res = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a,long_setting_name',
        'context_filters': 'theme:*,trust:(full,none)',
        'include_metadata': str(metadata)
    })

    expected = {
        'settings': {
            'a': {'rules': [
                {'context_features': [['trust', 'full']], 'value': 1, 'rule_id': 1},
                {'context_features': [['theme', 'black']], 'value': 2, 'rule_id': 2},
                {'context_features': [['trust', 'full'], ['theme', 'black']], 'value': 3, 'rule_id': 3},
            ]},
            'long_setting_name': {'rules': [
                {'context_features': [['trust', 'none']], 'value': 4, 'rule_id': 4},
            ]}
        }
    }
    if metadata:
        patch_rule_expectation_with_metadata(expected)

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_wildcard_only(metadata: bool, app_client, setup_rules):
    res = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a,long_setting_name',
        'context_filters': 'theme:*',
        'include_metadata': str(metadata)
    })

    expected = {
        'settings': {
            'a': {'rules': [
                {'context_features': [['theme', 'black']], 'value': 2, 'rule_id': 2},
            ]},
            'long_setting_name': {'rules': []}
        }
    }
    if metadata:
        patch_rule_expectation_with_metadata(expected)

    assert res.json() == expected


@mark.asyncio
async def test_query_rules_bad_contexts(app_client, setup_rules):
    res = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a,long_setting_name',
        'context_filters': 'theme:(black),trust:(full,part),love:(overflowing)'
    })
    assert res.status_code == 404


@mark.asyncio
async def test_query_rules_empty_contexts(app_client, setup_rules):
    res = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a,long_setting_name',
        'context_filters': 'trust:()'
    })
    assert res.status_code == 422


@mark.asyncio
async def test_query_rules_bad_settings(app_client, setup_rules):
    res = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a,d',
        'context_filters': 'trust:(full,part),theme:(black)'
    })
    assert res.status_code == 404


@mark.asyncio
@mark.parametrize('options', ['null', '**', 'wildcard'])
async def test_query_rules_bad_options(app_client, setup_rules, options):
    res = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a',
        'context_filters': options,
    })
    assert res.status_code == 422, res.content


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_nosettings(metadata: bool, app_client, setup_rules):
    res = await app_client.get('/api/v1/rules/query', query_string={
        'settings': '',
        'include_metadata': str(metadata)
    })
    res.raise_for_status()

    expected = {'settings': {}}

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_allsettings_no_filter(metadata: bool, app_client, setup_rules):
    res = await app_client.get('/api/v1/rules/query', query_string={
        'include_metadata': str(metadata)
    })
    res.raise_for_status()

    expected = {'settings': {
        'a': {'rules': [
            {'context_features': [['trust', 'full']], 'value': 1, 'rule_id': 1},
            {'context_features': [['theme', 'black']], 'value': 2, 'rule_id': 2},
            {'context_features': [['trust', 'full'], ['theme', 'black']], 'value': 3, 'rule_id': 3},
            {'context_features': [['user', 'admin'], ['theme', 'black']], 'value': 7, 'rule_id': 7},
        ]},
        'b': {'rules': [
            {'context_features': [['trust', 'full']], 'value': 6, 'rule_id': 6},
        ]},
        'long_setting_name': {'rules': [
            {'context_features': [['trust', 'none']], 'value': 4, 'rule_id': 4},
            {'context_features': [['trust', 'part']], 'value': 5, 'rule_id': 5},
        ]}
    }}

    if metadata:
        patch_rule_expectation_with_metadata(expected)

    assert res.json() == expected


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_rules_allsettings_with_filter(metadata: bool, app_client, setup_rules):
    res = await app_client.get('/api/v1/rules/query', query_string={
        'context_filters': 'user:*,trust:(full),theme:(blue)',
        'include_metadata': str(metadata)
    })
    res.raise_for_status()

    expected = {'settings': {
        'a': {'rules': [
            {'context_features': [['trust', 'full']], 'value': 1, 'rule_id': 1},
        ]},
        'b': {'rules': [
            {'context_features': [['trust', 'full']], 'value': 6, 'rule_id': 6},
        ]},
        'long_setting_name': {'rules': []}
    }}

    if metadata:
        patch_rule_expectation_with_metadata(expected)

    assert res.json() == expected


@fixture(params=['deprecated', 'new'])
def patch_callback(request):
    def callback(client, rule_name, value):
        if request.param == 'deprecated':
            return client.patch(f'/api/v1/rules/{rule_name}', data=json.dumps({'value': value}))
        else:
            return client.put(f'/api/v1/rules/{rule_name}/value', data=json.dumps({'value': value}))

    return callback


@mark.asyncio
async def test_patch_rule_sanity(patch_callback, example_rule, app_client):
    res = await patch_callback(app_client, example_rule, 5)
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
async def test_patch_rule_missing(patch_callback, app_client):
    res = await patch_callback(app_client, '50000', 5)
    assert res.status_code == 404


@mark.asyncio
async def test_patch_rule_bad_data(patch_callback, example_rule, app_client):
    res = await patch_callback(app_client, example_rule, ['d5'])
    assert res.status_code == 400


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_etag(app_client, setup_rules, metadata):
    res = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a,long_setting_name',
        'context_filters': 'theme:*,trust:(full,none)',
        'include_metadata': str(metadata)
    })
    res.raise_for_status()

    etag = res.headers['ETag']

    repeat_resp = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a,long_setting_name',
        'context_filters': 'theme:*,trust:(full,none)',
        'include_metadata': str(metadata)
    }, headers={'If-None-Match': etag})

    assert repeat_resp.status_code == 304
    assert repeat_resp.headers['ETag'] == etag
    assert repeat_resp.content == b'{"detail":"Not Modified"}'


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_wrong_etag(app_client, setup_rules, metadata):
    res = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a,long_setting_name',
        'context_filters': 'theme:*,trust:(full,none)',
        'include_metadata': str(metadata)
    })
    res.raise_for_status()

    etag = res.headers['ETag']
    wrong_etag = etag[:5] + '%' + etag[5:]

    repeat_resp = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a,long_setting_name',
        'context_filters': 'theme:*,trust:(full,none)',
        'include_metadata': str(metadata)
    }, headers={'If-None-Match': wrong_etag})

    assert repeat_resp.status_code == 200
    assert repeat_resp.headers['ETag'] == etag
    assert repeat_resp.content


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_etag_wildcard(app_client, setup_rules, metadata):
    repeat_resp = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a,long_setting_name',
        'context_filters': 'theme:*,trust:(full,none)',
        'include_metadata': str(metadata)
    }, headers={'If-None-Match': '*'})

    assert repeat_resp.status_code == 304
    assert repeat_resp.content == b'{"detail":"Not Modified"}'


@mark.asyncio
@mark.parametrize('metadata', [False, True])
async def test_query_repeat_filter(app_client, setup_rules, metadata):
    res = await app_client.get('/api/v1/rules/query', query_string={
        'settings': 'a,long_setting_name',
        'context_filters': 'theme:*,trust:(full,none),theme:*',
        'include_metadata': str(metadata)
    })
    assert res.status_code == 400
