from heksher._version import __version__
from heksher.api.v1 import router as v1_router
from heksher.app import HeksherApp

app = HeksherApp(title="Heksher", version=__version__ or "0.0.1")

app.include_router(v1_router)


@app.on_event('startup')
async def startup():
    await app.startup()


@app.on_event('shutdown')
async def shutdown():
    await app.shutdown()

app.health_monitor.add_fastapi_route(app)


def main():
    import uvicorn

    uvicorn.run(app, debug=True, host="0.0.0.0", port=8888)


if __name__ == "__main__":  # pragma: no cover
    main()
