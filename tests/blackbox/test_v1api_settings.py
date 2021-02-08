import json

from pytest import fixture, mark


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
        'changed': [],
        'incomplete': {}
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


@mark.parametrize('type_', [15, 'Flags{1,2,3}', 'enum[1,2,3]'])
def test_declare_new_setting_bad_type(app_client, type_):
    res = app_client.put('api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': type_,
        'default_value': 200.5,
        'metadata': {'testing': True}
    }))
    assert res.status_code == 422


def test_declare_new_setting_bad_default(app_client):
    res = app_client.put('api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200.5,
        'metadata': {'testing': True}
    }))
    assert res.status_code == 422


def test_declare_new_setting_bad_cf(app_client):
    res = app_client.put('api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme', 'color'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True}
    }))
    assert res.status_code == 422


def test_declare_new_setting_modify_bad_cf(size_limit_setting, app_client):
    res = app_client.put('api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme', 'color'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True}
    }))
    assert res.status_code == 422


def test_declare_no_modify(size_limit_setting, app_client):
    res = app_client.put('api/v1/settings/declare', data=json.dumps({
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
        'changed': [],
        'incomplete': {}
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
        'changed': [
            'configurable_features',
            'default_value',
            'metadata.ctr',
            'metadata.dummy',
        ],
        'incomplete': {}
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


def test_declare_incomplete(size_limit_setting, app_client):
    res = app_client.put('api/v1/settings/declare', data=json.dumps({
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

    res = app_client.get('api/v1/settings/size_limit')
    res.raise_for_status()
    assert res.json() == {
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True}
    }


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


def test_delete_setting_missing(size_limit_setting, app_client):
    res = app_client.delete('api/v1/settings/size_limit2')
    assert res.status_code == 404


@mark.parametrize('additional_data', [False, None])
def test_get_settings(app_client, additional_data):
    def mk_setting(name: str):
        res = app_client.put('api/v1/settings/declare', data=json.dumps({
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

    mk_setting('a')
    mk_setting('c')
    mk_setting('b')

    request_data = {}
    if additional_data is not None:
        request_data['include_additional_data'] = additional_data

    res = app_client.get('api/v1/settings', data=json.dumps(request_data))
    res.raise_for_status()
    assert res.json() == {
        'settings': [
            {'name': 'a'},
            {'name': 'b'},
            {'name': 'c'},
        ]
    }


def test_get_settings_additional_data(app_client):
    def mk_setting(name: str, type: str):
        res = app_client.put('api/v1/settings/declare', data=json.dumps({
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

    mk_setting('a', 'int')
    mk_setting('c', 'float')
    mk_setting('b', 'str')

    res = app_client.get('api/v1/settings', params={
        'include_additional_data': True
    })
    res.raise_for_status()
    assert res.json() == {
        'settings': [
            {'name': 'a', 'type': 'int', 'configurable_features': ['user', 'theme'],
             'metadata': {}, 'default_value': None},
            {'name': 'b', 'type': 'str', 'configurable_features': ['user', 'theme'],
             'metadata': {}, 'default_value': None},
            {'name': 'c', 'type': 'float', 'configurable_features': ['user', 'theme'],
             'metadata': {}, 'default_value': None},
        ]
    }
