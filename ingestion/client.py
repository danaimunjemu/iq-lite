import asyncio
import json
import logging
import websockets
from typing import List, Callable, Optional
from .models import Tick

logger = logging.getLogger(__name__)

class DerivClient:
    def __init__(self, app_id: int, api_token: Optional[str] = None):
        self.url = f"wss://api.derivws.com/trading/v1/options/ws/public?app_id={app_id}"
        self.api_token = api_token
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.subscriptions = []
        self._running = False

    async def connect(self):
        """Connects to Deriv WebSocket and authenticates if token is provided."""
        logger.info(f"Connecting to {self.url}...")
        self.ws = await websockets.connect(self.url)
        
        if self.api_token:
            await self.ws.send(json.dumps({"authorize": self.api_token}))
            auth_resp = await self.ws.recv()
            logger.info(f"Auth Response: {auth_resp}")

    async def subscribe_ticks(self, symbols: List[str], callback: Callable[[Tick], None]):
        """Subscribes to real-time ticks for multiple symbols."""
        self.subscriptions.extend(symbols)
        self._running = True
        
        # Subscribe to each symbol
        for symbol in symbols:
            await self.ws.send(json.dumps({"ticks": symbol, "subscribe": 1}))

        # Start listening loop
        await self._listen(callback)

    async def _listen(self, callback: Callable[[Tick], None]):
        while self._running:
            try:
                message = await self.ws.recv()
                data = json.loads(message)
                
                if "tick" in data:
                    tick_data = data["tick"]
                    tick = Tick(
                        symbol=tick_data["symbol"],
                        price=float(tick_data["quote"]),
                        epoch=int(tick_data["epoch"])
                    )
                    await callback(tick)
                elif "error" in data:
                    logger.error(f"API Error: {data['error']['message']}")
                
            except websockets.ConnectionClosed:
                logger.warning("WebSocket connection closed. Attempting reconnect...")
                await self._reconnect(callback)
                break
            except Exception as e:
                logger.error(f"Error in listener: {e}")
                await asyncio.sleep(1)

    async def _reconnect(self, callback: Callable[[Tick], None]):
        """Handles reconnection and re-subscribing."""
        backoff = 1
        while self._running:
            try:
                await self.connect()
                # Re-subscribe to all symbols
                for symbol in self.subscriptions:
                    await self.ws.send(json.dumps({"ticks": symbol, "subscribe": 1}))
                logger.info("Reconnected successfully.")
                await self._listen(callback)
                break
            except Exception as e:
                logger.error(f"Reconnect failed: {e}. Retrying in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def fetch_historical_ticks(self, symbol: str, start_time: int, end_time: int) -> List[Tick]:
        """Fetches historical ticks using the ticks_history API."""
        if not self.ws:
            await self.connect()
            
        request = {
            "ticks_history": symbol,
            "start": start_time,
            "end": end_time,
            "style": "ticks",
            "adjust_start_time": 1
        }
        await self.ws.send(json.dumps(request))
        response = await self.ws.recv()
        data = json.loads(response)
        
        ticks = []
        if "history" in data:
            history = data["history"]
            times = history["times"]
            prices = history["prices"]
            for t, p in zip(times, prices):
                ticks.append(Tick(symbol=symbol, price=float(p), epoch=int(t)))
        
        return ticks

    async def fetch_active_symbols(self, landing_company: Optional[str] = None) -> List[dict]:
        """Fetches the list of active symbols from Deriv."""
        if not self.ws:
            await self.connect()
            
        request = {"active_symbols": "brief"}
        if landing_company:
            request["landing_company"] = landing_company
            
        await self.ws.send(json.dumps(request))
        response = await self.ws.recv()
        data = json.loads(response)
        
        if "error" in data:
            logger.error(f"Active Symbols Error: {data['error']['message']}")
            
        return data.get("active_symbols", [])

    def stop(self):
        self._running = False
