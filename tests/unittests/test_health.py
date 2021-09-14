def test_health(app_client):
    app_client.get('/api/health').raise_for_status()


def test_unhealthy(app_client, mock_engine):
    mock_engine.connection.execute.side_effect = Exception
    assert app_client.get('/api/health').status_code == 500
