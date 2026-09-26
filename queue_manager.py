import asyncio
import itertools
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, List, Optional

from config import (
    ADMIN_IDS,
    COOLDOWN_SECONDS,
    DAILY_LIMIT_PER_USER,
    MAX_CONCURRENT_DOWNLOADS,
    MAX_JOBS_PER_USER,
    MAX_QUEUE_SIZE,
)
from database import count_downloads_since, get_user_daily_limit

_job_ids = itertools.count(1)


@dataclass
class Job:
    user_id: int
    chat_id: int
    url: str
    quality: str
    status_message: object  # aiogram Message the bot edits with progress
    id: int = field(default_factory=lambda: next(_job_ids))
    created_at: float = field(default_factory=time.time)
    cancelled: bool = False
    started: bool = False


class LimitError(Exception):
    """Raised when a user cannot enqueue a new job. Message is user-facing."""


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def get_daily_limit(user_id: int) -> int:
    """0 means unlimited."""
    if is_admin(user_id):
        return 0
    personal = get_user_daily_limit(user_id)
    return personal if personal is not None else DAILY_LIMIT_PER_USER


class DownloadQueue:
    """FIFO queue with a fixed number of workers and per-user limits."""

    def __init__(self, handler: Callable[[Job], Awaitable[None]], workers: int = MAX_CONCURRENT_DOWNLOADS):
        self._handler = handler
        self._workers_count = max(1, workers)
        self._queue: asyncio.Queue = asyncio.Queue()
        self._waiting: List[Job] = []
        self._running: Dict[int, Job] = {}
        self._last_submit: Dict[int, float] = {}
        self._workers: List[asyncio.Task] = []

    def start(self):
        for i in range(self._workers_count):
            self._workers.append(asyncio.create_task(self._worker(i)))
        logging.info(f"Download queue started with {self._workers_count} workers")

    # ---- limits ----

    def user_jobs(self, user_id: int) -> List[Job]:
        running = [j for j in self._running.values() if j.user_id == user_id]
        waiting = [j for j in self._waiting if j.user_id == user_id]
        return running + waiting

    def check_limits(self, user_id: int, check_cooldown: bool = True):
        """Raise LimitError if the user may not add a job right now."""
        if is_admin(user_id):
            return

        now = time.time()
        last = self._last_submit.get(user_id, 0)
        if check_cooldown and now - last < COOLDOWN_SECONDS:
            wait = int(COOLDOWN_SECONDS - (now - last)) + 1
            raise LimitError(f"⏱ Не так быстро! Подожди {wait} сек. перед следующей ссылкой.")

        active = len(self.user_jobs(user_id))
        if active >= MAX_JOBS_PER_USER:
            raise LimitError(
                f"🚦 У тебя уже {active} загрузк(и) в работе/очереди (максимум {MAX_JOBS_PER_USER}).\n"
                "Дождись окончания или отмени через /cancel."
            )

        limit = get_daily_limit(user_id)
        if limit:
            used = count_downloads_since(user_id, 24)
            if used + active >= limit:
                raise LimitError(
                    f"📊 Лимит исчерпан: {used}/{limit} скачиваний за последние 24 часа.\n"
                    "Попробуй позже 🙏"
                )

        if len(self._waiting) >= MAX_QUEUE_SIZE:
            raise LimitError("😵 Очередь переполнена. Попробуй через несколько минут.")

    # ---- queue ops ----

    def submit(self, job: Job) -> int:
        """Enqueue a job. Returns its position in the waiting list (0 = starts right away)."""
        self._waiting.append(job)
        self._queue.put_nowait(job)
        self._last_submit[job.user_id] = time.time()
        free_workers = self._workers_count - len(self._running)
        return max(0, len(self._waiting) - free_workers)

    def position(self, job: Job) -> Optional[int]:
        """1-based position among waiting jobs, None if not waiting."""
        try:
            return self._waiting.index(job) + 1
        except ValueError:
            return None

    def cancel_user_jobs(self, user_id: int) -> int:
        """Cancel waiting (not yet started) jobs of a user."""
        cancelled = 0
        for job in list(self._waiting):
            if job.user_id == user_id:
                job.cancelled = True
                self._waiting.remove(job)
                cancelled += 1
        return cancelled

    @property
    def running_count(self) -> int:
        return len(self._running)

    @property
    def waiting_count(self) -> int:
        return len(self._waiting)

    async def _worker(self, index: int):
        while True:
            job: Job = await self._queue.get()
            try:
                if job.cancelled:
                    continue
                if job in self._waiting:
                    self._waiting.remove(job)
                job.started = True
                self._running[job.id] = job
                logging.info(f"[worker {index}] Job {job.id} started: user={job.user_id} url={job.url} q={job.quality}")
                await self._handler(job)
            except Exception as e:
                logging.error(f"[worker {index}] Job {job.id} crashed: {e}", exc_info=True)
            finally:
                self._running.pop(job.id, None)
                self._queue.task_done()
