def test_get_all(app_client):
    response = app_client.get('/api/v1/context_features/')
    response.raise_for_status()
    assert response.json() == {
        'context_features': ["user", "trust", "theme"]
    }


def test_is_context_feature(app_client):
    response = app_client.get('/api/v1/context_features/trust')
    response.raise_for_status()
    assert not response.content


def test_is_not_context_feature(app_client):
    response = app_client.get('/api/v1/context_features/not-real')
    assert response.status_code == 404
    assert not response.content
