import json
from datetime import datetime
from itertools import chain

from pytest import fixture, mark


@fixture
def example_rule(size_limit_setting, app_client):
    res = app_client.post('/api/v1/rules', data=json.dumps({
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


def test_add_rule(example_rule, app_client):
    res = app_client.get(f'/api/v1/rules/{example_rule}')
    res.raise_for_status()
    assert res.json() == {
        'setting': 'size_limit',
        'value': 10,
        'feature_values': [['theme', 'bright']],
        'metadata': {'test': True}
    }


def test_add_rule_no_conds(size_limit_setting, app_client):
    res = app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {},
        'value': 10,
        'metadata': {'test': True}
    }))
    assert res.status_code == 422


def test_add_rule_missing_setting(app_client):
    res = app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit_2',
        'feature_values': {'theme': 'bright'},
        'value': 10,
        'metadata': {'test': True}
    }))
    assert 400 <= res.status_code <= 499


def test_add_rule_non_configurable(size_limit_setting, app_client):
    res = app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {'trust': 'full'},
        'value': 10,
        'metadata': {'test': True}
    }))
    assert 400 <= res.status_code <= 499


def test_add_rule_bad_type(size_limit_setting, app_client):
    res = app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {'theme': 'bright'},
        'value': True,
        'metadata': {'test': True}
    }))
    assert 400 <= res.status_code <= 499


def test_add_rule_existing(example_rule, app_client):
    res = app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {'theme': 'bright'},
        'value': 10,
        'metadata': {'test': True}
    }))
    assert res.status_code == 409


def test_block_injection(example_rule, app_client):
    res = app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {'theme': "' OR 1='1"},
        'value': 10,
        'metadata': {'test': True}
    }))
    assert res.status_code == 422


def test_delete_rule(example_rule, app_client):
    res = app_client.delete(f'/api/v1/rules/{example_rule}')
    res.raise_for_status()
    res = app_client.get(f'/api/v1/rules/{example_rule}')
    assert res.status_code == 404


def test_delete_rule_missing(example_rule, app_client):
    res = app_client.delete(f'/api/v1/rules/{example_rule + 1}')
    assert res.status_code == 404


def test_get_rule_missing(example_rule, app_client):
    res = app_client.get(f'/api/v1/rules/{example_rule + 1}')
    assert res.status_code == 404


def test_search_rule(example_rule, app_client, sql_service):
    res = app_client.get('/api/v1/rules/search', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': [('theme', 'bright')]
    }))
    res.raise_for_status()
    assert res.json() == {
        'rule_id': example_rule
    }


def test_search_rule_empty(example_rule, app_client, sql_service):
    res = app_client.get('/api/v1/rules/search', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': []
    }))
    assert res.status_code == 422


def test_search_rule_missing(example_rule, app_client):
    res = app_client.get('/api/v1/rules/search', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': [('theme', 'dark')]
    }))
    assert res.status_code == 404


@fixture
def mk_setting(app_client):
    def mk_setting(name: str):
        res = app_client.put('api/v1/settings/declare', data=json.dumps({
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
    def mk_rule(setting_name, features, val):
        res = app_client.post('/api/v1/rules', data=json.dumps({
            'setting': setting_name,
            'feature_values': features,
            'value': val,
            'metadata': {'test': 'yes'}
        }))
        res.raise_for_status()
        assert res.json().keys() == {'rule_id'}

    return mk_rule


@fixture
def setup_rules(mk_setting, mk_rule):
    mk_setting('a')
    mk_setting('b')
    mk_setting('c')

    mk_rule('a', {'trust': 'full'}, 1)
    mk_rule('a', {'theme': 'black'}, 2)
    mk_rule('a', {'theme': 'black', 'trust': 'full'}, 3)
    mk_rule('b', {'trust': 'none'}, 4)
    mk_rule('b', {'trust': 'part'}, 5)
    mk_rule('c', {'trust': 'full'}, 6)
    mk_rule('a', {'theme': 'black', 'user': 'admin'}, 7)


@mark.parametrize('metadata', [False, True])
def test_query_rules(metadata: bool, app_client, setup_rules):
    res = app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {'trust': ['full', 'part'], 'theme': ['black']},
        'include_metadata': metadata
    }))

    expected = {
        'rules': {
            'a': [
                {'context_features': [['trust', 'full']], 'value': 1},
                {'context_features': [['theme', 'black']], 'value': 2},
                {'context_features': [['trust', 'full'], ['theme', 'black']], 'value': 3}
            ],
            'b': [
                {'context_features': [['trust', 'part']], 'value': 5}
            ]
        }
    }
    if metadata:
        for rule in chain.from_iterable(expected['rules'].values()):
            rule['metadata'] = {'test': 'yes'}

    assert res.json() == expected


@mark.parametrize('metadata', [False, True])
def test_query_rules_time_cache(metadata: bool, app_client, setup_rules, mk_rule):
    current_time = datetime.now()
    # touch a to change its last_touch_time
    mk_rule('a', {'theme': 'grey', 'user': 'admin'}, 8)

    res = app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {'trust': ['full', 'part'], 'theme': ['black']},
        'include_metadata': metadata,
        'cache_time': current_time.isoformat(),
    }))

    expected = {
        'rules': {
            'a': [
                {'context_features': [['trust', 'full']], 'value': 1},
                {'context_features': [['theme', 'black']], 'value': 2},
                {'context_features': [['trust', 'full'], ['theme', 'black']], 'value': 3}
            ],
        }
    }
    if metadata:
        for rule in chain.from_iterable(expected['rules'].values()):
            rule['metadata'] = {'test': 'yes'}

    assert res.json() == expected


@mark.parametrize('metadata', [False, True])
def test_query_rules_fully_cached(metadata: bool, app_client, setup_rules, mk_rule):
    current_time = datetime.now()

    res = app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {'trust': ['full', 'part'], 'theme': ['black']},
        'include_metadata': metadata,
        'cache_time': current_time.isoformat(),
    }))

    expected = {
        'rules': {}
    }

    assert res.json() == expected


@mark.parametrize('metadata', [False, True])
def test_query_rules_with_empty(metadata: bool, app_client, setup_rules, sql_service):
    with sql_service.connection() as connection:
        connection.execute("""
        INSERT INTO rules (setting, value, metadata) VALUES ('b', '10', '{"test": "yes"}')
        """)

    res = app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {'trust': ['full', 'part'], 'theme': ['black']},
        'include_metadata': metadata
    }))

    expected = {
        'rules': {
            'a': [
                {'context_features': [['trust', 'full']], 'value': 1},
                {'context_features': [['theme', 'black']], 'value': 2},
                {'context_features': [['trust', 'full'], ['theme', 'black']], 'value': 3}
            ],
            'b': [
                {'context_features': [['trust', 'part']], 'value': 5},
                {'context_features': [], 'value': 10}
            ]
        }
    }
    if metadata:
        for rule in chain.from_iterable(expected['rules'].values()):
            rule['metadata'] = {'test': 'yes'}

    assert res.json() == expected


@mark.parametrize('metadata', [False, True])
def test_query_rules_nooptions(metadata: bool, app_client, setup_rules):
    res = app_client.get('/api/v1/rules/query', data=json.dumps({
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


@mark.parametrize('metadata', [False, True])
def test_query_rules_nooptions_with_matchall(metadata: bool, app_client, setup_rules, sql_service):
    with sql_service.connection() as connection:
        connection.execute("""
        INSERT INTO rules (setting, value, metadata) VALUES ('b', '10', '{"test": "yes"}')
        """)

    res = app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {},
        'include_metadata': metadata
    }))

    expected = {
        'rules': {
            'a': [],
            'b': [
                {'context_features': [], 'value': 10},
            ]
        }
    }

    if metadata:
        for rule in chain.from_iterable(expected['rules'].values()):
            rule['metadata'] = {'test': 'yes'}

    assert res.json() == expected


@mark.parametrize('metadata', [False, True])
def test_query_rules_matchall(metadata: bool, app_client, setup_rules):
    res = app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': '*',
        'include_metadata': metadata
    }))

    expected = {
        'rules': {
            'a': [
                {'context_features': [['trust', 'full']], 'value': 1},
                {'context_features': [['theme', 'black']], 'value': 2},
                {'context_features': [['trust', 'full'], ['theme', 'black']], 'value': 3},
                {'context_features': [['user', 'admin'], ['theme', 'black']], 'value': 7}
            ],
            'b': [
                {'context_features': [['trust', 'none']], 'value': 4},
                {'context_features': [['trust', 'part']], 'value': 5}
            ]
        }
    }
    if metadata:
        for rule in chain.from_iterable(expected['rules'].values()):
            rule['metadata'] = {'test': 'yes'}

    assert res.json() == expected


def test_query_rules_bad_contexts(app_client, setup_rules):
    res = app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {'trust': ['full', 'part'], 'theme': ['black'], 'love': ['overflowing']},
    }))
    assert 400 <= res.status_code <= 499


def test_query_rules_bad_settings(app_client, setup_rules):
    res = app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'd'],
        'context_features_options': {'trust': ['full', 'part'], 'theme': ['black']},
    }))
    assert 400 <= res.status_code <= 499


@mark.parametrize('options', [None, '**', 'wildcard'])
def test_query_rules_bad_options(app_client, setup_rules, options):
    res = app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a'],
        'context_features_options': options,
    }))
    assert res.status_code == 422, res.content
