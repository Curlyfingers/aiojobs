from functools import wraps

from aiohttp.web import View

from . import create_scheduler

__all__ = ('setup', 'spawn', 'get_scheduler', 'get_scheduler_from_app',
           'atomic')


def get_scheduler(request):
    scheduler = get_scheduler_from_request(request)
    if scheduler is None:
        raise RuntimeError(
            "Call aiojobs.aiohttp.setup() on application initialization")
    return scheduler


def get_scheduler_from_app(app):
    return app.get('AIOJOBS_SCHEDULER')


def get_scheduler_from_request(request):
    return request.config_dict.get('AIOJOBS_SCHEDULER')


async def spawn(request, coro, *args, **kwargs):
    return await get_scheduler(request).spawn(coro, *args, **kwargs)


def atomic(coro):
    @wraps(coro)
    async def wrapper(request, *args, **kwargs):
        job = await spawn(
            request.request if isinstance(request, View) else request,
            coro, request, *args, **kwargs
        )
        return await job.wait()
    return wrapper


def setup(app, **kwargs):
    async def on_startup(app):
        app['AIOJOBS_SCHEDULER'] = await create_scheduler(**kwargs)

    async def on_cleanup(app):
        await app['AIOJOBS_SCHEDULER'].close()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
