import asyncio
from typing import List, Callable, Coroutine
from models.trading import Tick
from data.manager import StorageHandler

class TickBuffer:
    def __init__(self, storage: StorageHandler, max_size: int = 100, flush_interval: float = 5.0):
        self.storage = storage
        self.max_size = max_size
        self.flush_interval = flush_interval
        self._buffer: List[Tick] = []
        self._lock = asyncio.Lock()
        self._flush_task = asyncio.create_task(self._periodic_flush())

    async def add_tick(self, tick: Tick):
        async with self._lock:
            self._buffer.append(tick)
            if len(self._buffer) >= self.max_size:
                await self._flush()

    async def _periodic_flush(self):
        while True:
            await asyncio.sleep(self.flush_interval)
            await self._flush()

    async def _flush(self):
        async with self._lock:
            if not self._buffer:
                return
            
            ticks_to_write = list(self._buffer)
            self._buffer.clear()
            await self.storage.write(ticks_to_write)

    async def close(self):
        self._flush_task.cancel()
        await self._flush()  # Final flush
