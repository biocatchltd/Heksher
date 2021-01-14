def test_health(app_client):
    app_client.get('/api/health').raise_for_status()
