from starlette.responses import JSONResponse

from heksher._version import __version__
from heksher.app import HeksherApp

app = HeksherApp(title="Heksher", version=__version__ or "0.0.1")


@app.on_event('startup')
async def startup():
    await app.startup()


@app.on_event('shutdown')
async def shutdown():
    await app.shutdown()


@app.get("/api/readiness")
async def ready():
    """Check if the app is ready by doing nothing - so it will always return 200 after all connections
    connected successfully / failed"""
    pass


@app.get('/api/health')
async def health_check():
    """
    Check the health of the connections
    """
    is_healthy = await app.is_healthy()
    if is_healthy:
        return JSONResponse({'version': __version__}, status_code=500)
    return {'version': __version__}


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, debug=True, host="0.0.0.0", port=8888)
