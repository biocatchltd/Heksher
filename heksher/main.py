from logging import getLogger

from fastapi.exception_handlers import http_exception_handler
from starlette.responses import JSONResponse

from heksher._version import __version__
from heksher.api.v1 import router as v1_router
from heksher.app import HeksherApp

app = HeksherApp(title="Heksher", version=__version__ or "0.0.1")

app.include_router(v1_router)

logger = getLogger(__name__)


@app.on_event('startup')
async def startup():
    await app.startup()


@app.on_event('shutdown')
async def shutdown():
    await app.shutdown()


@app.get('/api/health')
async def health_check():
    """
    Check the health of the connections to the service
    """
    if app.doc_only:
        return JSONResponse({'version': __version__, 'doc_only': True})
    if not app.health_monitor.status:
        return JSONResponse({'version': __version__}, status_code=500)
    return {'version': __version__}


@app.exception_handler(Exception)
async def handle_exception(request, exc):
    logger.exception('unhandled exception', exc_info=exc, extra={'scope': request.scope})
    return await http_exception_handler(request, exc)


def main():
    import uvicorn

    uvicorn.run(app, debug=True, host="0.0.0.0", port=8888)


if __name__ == "__main__":  # pragma: no cover
    main()
