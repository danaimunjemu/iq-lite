import asyncio
import json
import logging
import websockets
from typing import List, Callable, Optional
from models.trading import Tick, Candle

logger = logging.getLogger(__name__)

class DerivClient:
    def __init__(self, app_id: int, api_token: Optional[str] = None):
        self.url = f"wss://api.derivws.com/trading/v1/options/ws/public?app_id={app_id}"
        self.api_token = api_token
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.subscriptions = []
        self._running = False
        
        # Multiplexing state
        self._req_id_counter = 0
        self._pending_requests = {}  # req_id: asyncio.Future
        self._tick_callback = None
        self._receiver_task = None

    async def connect(self):
        """Connects to Deriv WebSocket and starts the receiver loop."""
        if self.ws:
            return

        logger.info(f"Connecting to {self.url}...")
        self.ws = await websockets.connect(self.url)
        self._running = True
        
        # Start the central receiver loop
        if not self._receiver_task or self._receiver_task.done():
            self._receiver_task = asyncio.create_task(self._receiver_loop())
        
        if self.api_token:
            auth_resp = await self._request({"authorize": self.api_token})
            logger.info(f"Auth Response Status: {'Success' if 'authorize' in auth_resp else 'Failed'}")

    async def _receiver_loop(self):
        """Central loop to receive all messages and dispatch them."""
        while self._running:
            try:
                if not self.ws:
                    await asyncio.sleep(1)
                    continue

                message = await self.ws.recv()
                data = json.loads(message)
                
                # 1. Handle Request-Response (req_id)
                req_id = data.get("req_id")
                if req_id in self._pending_requests:
                    future = self._pending_requests.pop(req_id)
                    if not future.done():
                        future.set_result(data)
                
                # 2. Handle Ticks (unsolicited)
                elif "tick" in data and self._tick_callback:
                    tick_data = data["tick"]
                    tick = Tick(
                        symbol=tick_data["symbol"],
                        price=float(tick_data["quote"]),
                        epoch=int(tick_data["epoch"])
                    )
                    # We don't await the callback here to avoid blocking the receiver
                    asyncio.create_task(self._tick_callback(tick))
                
                # 3. Handle Errors
                elif "error" in data:
                    logger.error(f"API Error: {data['error']['message']}")
                    # If there's an error with a req_id, it will be handled above
                
            except websockets.ConnectionClosed:
                logger.warning("WebSocket connection closed. Attempting reconnect...")
                await self._handle_reconnect()
                break
            except Exception as e:
                logger.error(f"Error in receiver loop: {e}")
                await asyncio.sleep(1)

    async def _handle_reconnect(self):
        """Handles internal reconnection logic."""
        backoff = 1
        while self._running:
            try:
                await self.connect()
                # Re-subscribe to all symbols
                for symbol in self.subscriptions:
                    await self.ws.send(json.dumps({"ticks": symbol, "subscribe": 1, "req_id": self._next_id()}))
                logger.info("Reconnected successfully.")
                break
            except Exception as e:
                logger.error(f"Reconnect failed: {e}. Retrying in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    def _next_id(self) -> int:
        self._req_id_counter += 1
        return self._req_id_counter

    async def _request(self, payload: dict, timeout: int = 30) -> dict:
        """Sends a request with req_id and waits for the specific response."""
        if not self.ws:
            await self.connect()
            
        req_id = self._next_id()
        payload["req_id"] = req_id
        
        future = asyncio.get_running_loop().create_future()
        self._pending_requests[req_id] = future
        
        try:
            await self.ws.send(json.dumps(payload))
            return await asyncio.wait_for(future, timeout=timeout)
        except websockets.ConnectionClosed:
            logger.warning("Connection closed during request. Retrying after reconnect...")
            self.ws = None # Trigger reconnect
            await self.connect()
            await self.ws.send(json.dumps(payload))
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(req_id, None)
            raise TimeoutError(f"Request {req_id} timed out after {timeout}s")

    async def subscribe_ticks(self, symbols: List[str], callback: Callable[[Tick], None]):
        """Subscribes to real-time ticks for multiple symbols."""
        self.subscriptions.extend(symbols)
        self._tick_callback = callback
        
        # Send subscription requests
        for symbol in symbols:
            await self._request({"ticks": symbol, "subscribe": 1})

    async def fetch_historical_ticks(self, symbol: str, start_time: int, end_time: int) -> List[Tick]:
        """Fetches historical ticks using the ticks_history API."""
        request = {
            "ticks_history": symbol,
            "start": start_time,
            "end": end_time,
            "style": "ticks",
            "adjust_start_time": 1
        }
        data = await self._request(request)
        
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
        request = {"active_symbols": "brief"}
        if landing_company:
            request["landing_company"] = landing_company
            
        data = await self._request(request)
        return data.get("active_symbols", [])

    async def buy_contract(self, symbol: str, amount: float, action: str, dry_run: bool = True) -> dict:
        """Executes a trade on Deriv. If dry_run=True, it mocks the execution."""
        if dry_run:
            logger.info(f"[MOCK] Executing {action} on {symbol} for {amount:.2f} lots.")
            return {"status": "success", "msg": "Simulated execution successful", "contract_id": 999999}
            
        if not self.api_token:
            logger.error("Cannot execute live trade: No API Token provided.")
            return {"status": "error", "msg": "Missing API Token"}
            
        request = {
            "buy": 1,
            "price": amount,
            "parameters": {
                "amount": amount,
                "basis": "stake",
                "contract_type": "CALL" if action == "BUY" else "PUT",
                "currency": "USD",
                "duration": 60,
                "duration_unit": "m",
                "symbol": symbol
            }
        }
        
        data = await self._request(request)
        if "error" in data:
            logger.error(f"Execution Error: {data['error']['message']}")
            return {"status": "error", "msg": data["error"]["message"]}
            
        return data.get("buy", {})

    async def fetch_historical_candles(self, symbol: str, granularity: int, start_time: int, end_time: int) -> List[Candle]:
        """Fetches historical candles directly from the API using the candles style."""
        request = {
            "ticks_history": symbol,
            "start": start_time,
            "end": end_time,
            "granularity": granularity,
            "style": "candles",
            "adjust_start_time": 1
        }
        data = await self._request(request)
        
        candles = []
        if "candles" in data:
            for c in data["candles"]:
                candles.append(Candle(
                    symbol=symbol,
                    open=float(c["open"]),
                    high=float(c["high"]),
                    low=float(c["low"]),
                    close=float(c["close"]),
                    epoch=int(c["epoch"]),
                    is_closed=True
                ))
                
        return candles

    def stop(self):
        self._running = False
        if self._receiver_task:
            self._receiver_task.cancel()

