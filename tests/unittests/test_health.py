from pytest import mark


@mark.asyncio
async def test_health(app_client):
    (await app_client.get('/api/health')).raise_for_status()


@mark.asyncio
async def test_unhealthy(app_client, mock_engine):
    mock_engine.connection.execute.side_effect = Exception
    await app_client.application.health_monitor._set_status()
    assert (await app_client.get('/api/health')).status_code == 500
