import asyncio
import sys
import uuid
import traceback

import async_timeout


class Job:
    STATUS_UNKNOWN = 'unknown'
    STATUS_PENDING = 'pending'
    STATUS_ACTIVE = 'active'
    STATUS_CLOSED = 'closed'

    _task = None
    _uuid = None
    _closed = False
    _message = None
    _progress = 0
    _explicit = False
    _source_traceback = None

    def __init__(self, f, scheduler, loop, *args, **kwargs):
        assert asyncio.iscoroutinefunction(f)
        self._uuid = uuid.uuid4().hex
        self._coro = f(
            *args, job=self, scheduler=scheduler, loop=loop, **kwargs
        )
        self._loop = loop
        self._scheduler = scheduler
        self._started = loop.create_future()

        if loop.get_debug():
            self._source_traceback = traceback.extract_stack(sys._getframe(2))

    def __repr__(self):
        info = []
        if self._closed:
            info.append('closed')
        elif self._task is None:
            info.append('pending')
        info = ' '.join(info)
        if info:
            info += ' '
        return '<Job {}coro=<{}>>'.format(info, self._coro)

    @property
    def uuid(self):
        return self._uuid

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, v):
        assert isinstance(v, str)
        self._message = v

    @property
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, v):
        assert isinstance(v, int)
        self._progress = v

    @property
    def status(self):
        if self.active:
            return self.STATUS_ACTIVE
        if self.pending:
            return self.STATUS_PENDING
        if self.closed:
            return self.STATUS_CLOSED
        return self.STATUS_UNKNOWN

    @property
    def active(self):
        return not self.closed and not self.pending

    @property
    def pending(self):
        return self._task is None and not self.closed

    @property
    def closed(self):
        return self._closed

    async def _do_wait(self, timeout):
        with async_timeout.timeout(timeout=timeout, loop=self._loop):
            # TODO: add a test for waiting for a pending coro
            await self._started
            return await self._task

    async def wait(self, *, timeout=None):
        if self._closed:
            return
        self._explicit = True
        scheduler = self._scheduler
        try:
            return await asyncio.shield(self._do_wait(timeout),
                                        loop=self._loop)
        except asyncio.CancelledError:
            # Don't stop inner coroutine on explicit cancel
            raise
        except Exception:
            await self._close(scheduler.close_timeout)
            raise

    async def close(self, *, timeout=None):
        if self._closed:
            return
        self._explicit = True
        if timeout is None:
            timeout = self._scheduler.close_timeout
        await self._close(timeout)

    async def _close(self, timeout):
        self._closed = True
        if self._task is None:
            # the task is closed immediately without actual execution
            # it prevents a warning like
            # RuntimeWarning: coroutine 'coro' was never awaited
            self._start()
        if not self._task.done():
            self._task.cancel()
        # self._scheduler is None after _done_callback()
        scheduler = self._scheduler
        try:
            with async_timeout.timeout(timeout=timeout,
                                       loop=self._loop):
                await self._task
        except asyncio.CancelledError:
            pass
        except asyncio.TimeoutError as exc:
            if self._explicit:
                raise
            context = {'message': "Job closing timed out",
                       'job': self,
                       'exception': exc}
            if self._source_traceback is not None:
                context['source_traceback'] = self._source_traceback
            scheduler.call_exception_handler(context)
        except Exception as exc:
            if self._explicit:
                raise
            self._report_exception(exc)

    def _start(self):
        assert self._task is None
        self._task = self._loop.create_task(self._coro)
        self._task.add_done_callback(self._done_callback)
        self._started.set_result(None)

    def _done_callback(self, task):
        scheduler = self._scheduler
        scheduler._done(self)
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            pass
        else:
            if exc is not None and not self._explicit:
                self._report_exception(exc)
                scheduler._failed_tasks.put_nowait(task)
        self._scheduler = None  # drop backref
        self._closed = True

    def _report_exception(self, exc):
        context = {'message': "Job processing failed",
                   'job': self,
                   'exception': exc}
        if self._source_traceback is not None:
            context['source_traceback'] = self._source_traceback
        self._scheduler.call_exception_handler(context)
