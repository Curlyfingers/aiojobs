import asyncio
from contextlib import suppress
from unittest import mock

import pytest


async def test_job_spawned(scheduler):
    async def coro(**kwargs):
        pass
    job = await scheduler.spawn(coro)
    assert job.active
    assert not job.closed
    assert not job.pending
    assert 'closed' not in repr(job)
    assert 'pending' not in repr(job)

    assert repr(job).startswith('<Job')
    assert repr(job).endswith('>')


async def test_job_awaited(scheduler):
    async def coro(**kwargs):
        pass
    job = await scheduler.spawn(coro)
    await job.wait()

    assert not job.active
    assert job.closed
    assert not job.pending
    assert 'closed' in repr(job)
    assert 'pending' not in repr(job)


async def test_job_closed(scheduler):
    async def coro(**kwargs):
        pass
    job = await scheduler.spawn(coro)
    await job.close()

    assert not job.active
    assert job.closed
    assert not job.pending
    assert 'closed' in repr(job)
    assert 'pending' not in repr(job)


async def test_job_pending(make_scheduler):
    scheduler = await make_scheduler(limit=1)

    async def coro1(**kwargs):
        await asyncio.sleep(10)

    async def coro2(**kwargs):
        pass

    await scheduler.spawn(coro1)
    job = await scheduler.spawn(coro2)

    assert not job.active
    assert not job.closed
    assert job.pending
    assert 'closed' not in repr(job)
    assert 'pending' in repr(job)


# Mangle a name for satisfy 'pending' not in repr check
async def test_job_resume_after_p_e_nding(make_scheduler):
    scheduler = await make_scheduler(limit=1)

    async def coro1(**kwargs):
        await asyncio.sleep(10)

    async def coro2(**kwargs):
        pass

    job1 = await scheduler.spawn(coro1)
    job2 = await scheduler.spawn(coro2)

    await job1.close()

    assert job2.active
    assert not job2.closed
    assert not job2.pending
    assert 'closed' not in repr(job2)
    assert 'pending' not in repr(job2)


async def test_job_wait_result(make_scheduler):
    handler = mock.Mock()
    scheduler = await make_scheduler(exception_handler=handler)

    async def coro(**kwargs):
        return 1

    job = await scheduler.spawn(coro)
    ret = await job.wait()
    assert ret == 1
    assert not handler.called


async def test_job_wait_exception(make_scheduler):
    handler = mock.Mock()
    scheduler = await make_scheduler(exception_handler=handler)
    exc = RuntimeError()

    async def coro(**kwargs):
        raise exc

    job = await scheduler.spawn(coro)
    with pytest.raises(RuntimeError) as ctx:
        await job.wait()
    assert ctx.value is exc
    assert not handler.called


async def test_job_close_exception(make_scheduler):
    handler = mock.Mock()
    scheduler = await make_scheduler(exception_handler=handler)
    exc = RuntimeError()
    fut = asyncio.Future()

    async def coro(**kwargs):
        fut.set_result(None)
        raise exc

    job = await scheduler.spawn(coro)
    await fut

    with pytest.raises(RuntimeError):
        await job.close()
    assert not handler.called


async def test_job_close_timeout(make_scheduler):
    handler = mock.Mock()
    scheduler = await make_scheduler(exception_handler=handler,
                                     close_timeout=0.01)

    fut1 = asyncio.Future()
    fut2 = asyncio.Future()

    async def coro(**kwargs):
        fut1.set_result(None)
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            await fut2

    job = await scheduler.spawn(coro)
    await fut1

    with pytest.raises(asyncio.TimeoutError):
        await job.close()
    assert not handler.called


async def test_job_await_pending(make_scheduler, loop):
    scheduler = await make_scheduler(limit=1)

    fut = asyncio.Future()

    async def coro1(**kwargs):
        await fut

    async def coro2(**kwargs):
        return 1

    await scheduler.spawn(coro1)
    job = await scheduler.spawn(coro2)

    loop.call_later(0.01, fut.set_result, None)
    ret = await job.wait()
    assert ret == 1


async def test_job_cancel_awaiting(make_scheduler, loop):
    scheduler = await make_scheduler()

    fut = loop.create_future()

    async def f(**kwargs):
        await fut

    job = await scheduler.spawn(f)

    task = loop.create_task(job.wait())
    assert job.active, job
    await asyncio.sleep(0.05, loop=loop)
    assert job.active, job
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    assert not fut.cancelled()
    fut.set_result(None)


async def test_job_wait_closed(make_scheduler):
    scheduler = await make_scheduler(limit=1)
    fut = asyncio.Future()

    async def coro1(**kwargs):
        raise RuntimeError()

    async def coro2(**kwargs):
        fut.set_result(None)

    job = await scheduler.spawn(coro1)
    await scheduler.spawn(coro2)

    await fut
    await job.wait()


async def test_job_close_closed(make_scheduler):
    scheduler = await make_scheduler(limit=1)
    fut = asyncio.Future()

    async def coro1(**kwargs):
        raise RuntimeError()

    async def coro2(**kwargs):
        fut.set_result(None)

    job = await scheduler.spawn(coro1)
    await scheduler.spawn(coro2)

    await fut
    await job.close()
