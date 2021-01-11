import json

from pytest import fixture


@fixture
def size_limit_setting(app_client):
    res = app_client.put('api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True}
    }))
    res.raise_for_status()
    assert res.json() == {
        'created': True,
        'rewritten': []
    }


def test_declare_new_setting(size_limit_setting, app_client):
    res = app_client.get('api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True}
    }


def test_declare_modify(app_client):
    res = app_client.put('api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True, 'ctr': 1, 'dummy': 2}
    }))
    res.raise_for_status()
    assert res.json() == {
        'created': True,
        'rewritten': []
    }

    res = app_client.put('api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 300,
        'metadata': {'testing': True, 'ctr': 2}
    }))
    res.raise_for_status()
    assert res.json() == {
        'created': False,
        'rewritten': [
            'configurable_features',
            'default_value',
            'metadata.ctr',
            'metadata.dummy',
        ]
    }

    res = app_client.get('api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 300,
        'metadata': {'testing': True, 'ctr': 2}
    }


def test_declare_conflict(size_limit_setting, app_client):
    res = app_client.put('api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'str',
        'default_value': "200",
        'metadata': {'testing': True}
    }))
    assert res.status_code == 409


def test_get_setting(size_limit_setting, app_client):
    res = app_client.get('api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True}
    }


def test_get_setting_missing(app_client):
    res = app_client.get('api/v1/settings/size_limit')
    assert res.status_code == 404


def test_delete_setting(size_limit_setting, app_client):
    res = app_client.delete('api/v1/settings/size_limit')
    assert res.status_code == 204
    res = app_client.get('api/v1/settings/size_limit')
    assert res.status_code == 404


def test_get_settings(app_client):
    def mk_setting(name: str):
        res = app_client.put('api/v1/settings/declare', data=json.dumps({
            'name': name,
            'configurable_features': [],
            'type': 'int'
        }))
        res.raise_for_status()
        assert res.json() == {
            'created': True,
            'rewritten': []
        }

    mk_setting('a')
    mk_setting('c')
    mk_setting('b')

    res = app_client.get('api/v1/settings')
    res.raise_for_status()
    assert res.json() == {
        'settings': ['a', 'b', 'c']
    }
