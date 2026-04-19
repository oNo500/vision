import asyncio
from unittest.mock import AsyncMock

import pytest

from vision_intelligence.video_asr.jobs import JobManager


async def test_job_manager_tracks_asyncio_task():
    jm = JobManager()
    done = asyncio.Event()

    async def fake_job():
        await done.wait()

    job_id = jm.submit("job1", fake_job())
    assert jm.is_running(job_id)
    done.set()
    await jm.wait(job_id)
    assert not jm.is_running(job_id)


async def test_job_manager_captures_exception():
    jm = JobManager()

    async def boom():
        raise RuntimeError("boom")

    job_id = jm.submit("jobx", boom())
    await jm.wait(job_id)
    err = jm.get_error(job_id)
    assert err is not None and "boom" in err
