# Quant Trading System: Structural Blueprint

This document defines the architectural standard for the quantitative trading engine. It ensures a clean separation of concerns between data ingestion, signal engineering, risk management, and execution.

## 1. Directory Structure

```text
trading_engine/
├── api/             # Low-level Connectivity (REST/WebSockets)
├── analytics/       # Post-trade forensics & PnL reporting
├── backtesting/     # Historical simulation engine
├── config/          # Environment & Indicator settings
├── execution/       # Order management & Signal orchestrator
├── features/        # Technical indicators & signal engineering
├── logs/            # Runtime & Trade history audit logs
├── risk/            # Risk gating & position sizing
├── strategy/        # High-level decision logic
├── tests/           # Unit & Integration test suite
├── data/            # Local high-performance storage (Parquet/CSV)
└── main.py          # Central system entry point & orchestrator
```

## 2. Module Responsibilities

### api/ (Broker/Exchange Interface)
- **Purpose**: Authenticates and maintains connections to data providers and brokers.
- **Responsibilities**: WebSocket heartbeats, raw data normalization, and push-based order execution.
- **Example Files**: `broker_client.py`, `deriv_ws.py`.

### features/ (Signal Engineering)
- **Purpose**: Transforms raw data into actionable technical state.
- **Responsibilities**: Indicator calculation (RSI, EMA, etc.), volatility extraction, and statistical feature engineering.
- **Example Files**: `indicators.py`, `tick_window.py`.

### strategy/ (Decision Engine)
- **Purpose**: The core "Brain" that generates trading intentions.
- **Responsibilities**: Analyzing features to emit `TradeSignal` objects. Agnostic of broker-specific details.
- **Example Files**: `rsi_strategy.py`, `trend_follow_strat.py`.

### risk/ (The Defensive Gate)
- **Purpose**: Ensures every trade is safe and correctly sized.
- **Responsibilities**: Portfolio-level risk management, position sizing, drawdown protection, and kill-switches.
- **Example Files**: `pos_sizing.py`, `drawdown_limit.py`.

### execution/ (Order Lifecycle)
- **Purpose**: Converts abstract signals into concrete broker orders.
- **Responsibilities**: Order routing, fill monitoring, slippage tracking, and retry logic.
- **Example Files**: `order_manager.py`, `latency_tracking.py`.

---

## 3. Module Interaction & Lifecycle

1. **API** receives a tick -> Passes to **Features**.
2. **Features** updates its sliding windows -> Returns a **FeatureSet**.
3. **Strategy** evaluates the **FeatureSet** -> Emits a **TradeSignal**.
4. **Risk** inspects the **TradeSignal** -> Computes the **LotSize** and validates equity limits.
5. **Execution** converts everything into an **Order** and pushes it to the **API**.
6. **Analytics** logs the event for performance metrics calculation.

---

## 4. Best Practices for Modular Scalability
- **Dependency Injection**: Always pass the `APIClient` as a dependency into the `StrategyEngine` during initialization. This allows for seamless "Hot Swapping" between **Live** and **Backtest** modes.
- **Statelessness**: Features should be stateless (pure functions or state-aware buffers). This makes debugging and unit testing 10x easier.
- **Asyncio Orchestration**: Use an asynchronous loop in `main.py` to ensure that one slow API call doesn't block the entire tick-processing pipeline.
