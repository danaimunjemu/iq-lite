from abc import ABC, abstractmethod
from typing import List
import os
import csv
from .models import Tick

class StorageHandler(ABC):
    @abstractmethod
    async def write(self, ticks: List[Tick]):
        """Writes a batch of ticks to the storage medium."""
        pass

class CSVStorage(StorageHandler):
    def __init__(self, filename: str):
        self.filename = filename
        self._initialize_file()

    def _initialize_file(self):
        if not os.path.exists(self.filename):
            with open(self.filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=["symbol", "price", "epoch", "timestamp"])
                writer.writeheader()

    async def write(self, ticks: List[Tick]):
        if not ticks:
            return
            
        with open(self.filename, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["symbol", "price", "epoch", "timestamp"])
            for tick in ticks:
                writer.writerow(tick.to_dict())
        print(f"[Storage] Flushed {len(ticks)} ticks to {self.filename}")
