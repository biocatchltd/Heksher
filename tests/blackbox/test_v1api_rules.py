import json

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


def test_delete_rule(example_rule, app_client):
    res = app_client.delete(f'/api/v1/rules/{example_rule}')
    res.raise_for_status()
    res = app_client.get(f'/api/v1/rules/{example_rule}')
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


def test_search_rule_missing(example_rule, app_client):
    res = app_client.get('/api/v1/rules/search', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': [('theme', 'dark')]
    }))
    assert res.status_code == 404


@mark.parametrize('metadata', [False, True])
def test_query_rules(metadata: bool, app_client):
    def mk_setting(name: str):
        res = app_client.put('api/v1/settings/declare', data=json.dumps({
            'name': name,
            'configurable_features': ['theme', 'trust'],
            'type': 'int'
        }))
        res.raise_for_status()
        assert res.json() == {
            'created': True,
            'rewritten': []
        }

    def mk_rule(setting_name, features, val):
        res = app_client.post('/api/v1/rules', data=json.dumps({
            'setting': setting_name,
            'feature_values': features,
            'value': val,
        }))
        res.raise_for_status()
        assert res.json().keys() == {'rule_id'}

    mk_setting('a')
    mk_setting('b')
    mk_setting('c')

    mk_rule('a', {'trust': 'full'}, 1)
    mk_rule('a', {'theme': 'black'}, 2)
    mk_rule('b', {'trust': 'none'}, 3)
    mk_rule('b', {'trust': 'part'}, 4)
    mk_rule('c', {'trust': 'full'}, 5)

    res = app_client.get('/api/v1/rules/query', data=json.dumps({
        'setting_names': ['a', 'b'],
        'context_features_options': {'trust': ['full', 'part'], 'theme': ['black']},
        'include_metadata': metadata
    }))

    print(res.json())
