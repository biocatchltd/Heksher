def test_health(app_client):
    app_client.get('/api/health').raise_for_status()


def test_redoc(app_client):
    app_client.get('/redoc').raise_for_status()
