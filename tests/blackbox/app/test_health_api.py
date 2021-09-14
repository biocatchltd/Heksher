from pytest import mark


@mark.asyncio
async def test_health(app_client):
    (await app_client.get('/api/health')).raise_for_status()


@mark.asyncio
async def test_redoc(app_client):
    (await app_client.get('/redoc')).raise_for_status()
