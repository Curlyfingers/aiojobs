=======
aiojobs
=======
.. image:: https://travis-ci.org/aio-libs/aiojobs.svg?branch=master
    :target: https://travis-ci.org/aio-libs/aiojobs
.. image:: https://codecov.io/gh/aio-libs/aiojobs/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/aio-libs/aiojobs
.. image:: https://img.shields.io/pypi/v/aiojobs.svg
    :target: https://pypi.python.org/pypi/aiojobs
.. image:: https://readthedocs.org/projects/aiojobs/badge/?version=latest
    :target: http://aiojobs.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status
.. image:: https://badges.gitter.im/Join%20Chat.svg
    :target: https://gitter.im/aio-libs/Lobby
    :alt: Chat on Gitter

Jobs scheduler for managing background task (asyncio)

Changes:
    - passing parameters such as `scheduler`, `loop`, `job` to coroutine
    - you may pass positional and keyword arguments to coroutine
    - `spawn` method expects async function instead of coroutine and invoke it in schedule
    - added `uuid`, `status`, `message` and `progress` properties to track job
    - scheduler uses dictionary instead set to store tasks

The library gives controlled way for scheduling background tasks for
asyncio applications.

Installation
============

.. code-block:: bash

   $ pip3 install aiojobs

Usage example
=============

.. code-block:: python

   import asyncio
    import aiojobs


    async def long_task(timeout, job, *args, **kwargs):
        job.message = 'Long task started...'
        while job.progress < 100:
            job.message = 'Very important message from the task'
            job.progress += 10
            await asyncio.sleep(timeout)


    async def poll_task(target_id, frequency, scheduler, job, **kwargs):
        def show_status():
            print(
                f'Job UUID: {target_job.uuid},'
                f' status: {target_job.status},'
                f' message: {target_job.message},'
                f' progress: {target_job.progress}%'
            )
        print(f'Polling job UUID: {job.uuid} started')
        target_job = scheduler.jobs.get(target_id)
        if not target_id:
            return
        try:
            while True:
                show_status()
                await asyncio.sleep(1/frequency)
        except asyncio.CancelledError:
            pass
        finally:
            print(f'Polling job UUID: {job.uuid} stopped')


    async def main():
        scheduler = await aiojobs.create_scheduler()

        job = await scheduler.spawn(long_task, timeout=1)
        await scheduler.spawn(poll_task, target_id= job.uuid, frequency=2)

        await asyncio.sleep(15)
        # not all scheduled jobs are finished at the moment

        # gracefully close spawned jobs
        await scheduler.close()

    asyncio.get_event_loop().run_until_complete(main())


Integration with aiohttp.web
============================

.. code-block:: python

   from aiohttp import web
   from aiojobs.aiohttp import setup, spawn

   async def handler(request):
       await spawn(request, coro)
       return web.Response()

   app = web.Application()
   app.router.add_get('/', handler)
   setup(app)

or just

.. code-block:: python

   from aiojobs.aiohttp import atomic

   @atomic
   async def handler(request, *args, **kwargs):
       return web.Response()

For more information read documentation: https://aiojobs.readthedocs.io

Communication channels
======================

*aio-libs* google group: https://groups.google.com/forum/#!forum/aio-libs

Feel free to post your questions and ideas here.

*Gitter Chat* https://gitter.im/aio-libs/Lobby

We support `Stack Overflow <https://stackoverflow.com>`_.
Please add *python-asyncio* or *aiohttp* tag to your question there.


Author and License
==================

The ``aiojobs`` package is written by Andrew Svetlov.

It's *Apache 2* licensed and freely available.
