import logging
from abc import ABC, abstractmethod
from typing import List, Any
import os
import csv

logger = logging.getLogger(__name__)

class StorageHandler(ABC):
    @abstractmethod
    async def write(self, data: List[Any]):
        """Writes a batch of data items (ticks, candles) to storage."""
        pass

class CSVStorage(StorageHandler):
    """
    Schema-aware CSV storage for Ticks and Candles.
    """
    def __init__(self, filename: str, headers: List[str] = None):
        self.filename = filename
        self.headers = headers or ["symbol", "price", "epoch", "timestamp"]
        self._initialize_file()

    def _initialize_file(self):
        if os.path.exists(self.filename):
            # Try to read existing headers
            try:
                with open(self.filename, 'r', newline='') as f:
                    reader = csv.reader(f)
                    existing_headers = next(reader, None)
                    if existing_headers:
                        self.headers = existing_headers
            except Exception:
                pass
        else:
            # Create new file with provided headers
            os.makedirs(os.path.dirname(self.filename), exist_ok=True) if os.path.dirname(self.filename) else None
            with open(self.filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writeheader()

    async def write(self, data: List[Any]):
        """Writes a batch of ticks or candles to CSV."""
        if not data:
            return
            
        with open(self.filename, 'a', newline='') as f:
            # Dynamically use headers if not provided
            sample = data[0].to_dict()
            fieldnames = self.headers if self.headers else list(sample.keys())
            
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            for item in data:
                writer.writerow(item.to_dict())
        
        logger.info(f"[Storage] Flushed {len(data)} items to {self.filename}")
