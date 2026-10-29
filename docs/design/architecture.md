# System architecture

> **Data source change (Oct 2026):** the F1 live-timing archive and SignalR feed
> now return 401 (auth-gated). Phases 0–7 use **OpenF1 historical** instead; the
> ingest adapter normalises OpenF1 rows into our own `RawMessage`. The live source
> is decided in P8.1. To be redrawn in draw.io.

```text
                    ┌──────────────────────── INGEST ────────────────────────┐
                    │                                                        │
  OpenF1 historical │  OpenF1Adapter ───┐                                    │
  (past sessions)  ─┼─>  (P0.4 / P2.8)  │   RawMessage{topic, payload,       │
                    │                   ├─>          event_ts, ingest_ts}    │
  Live source       │  LiveAdapter ─────┘          │                         │
  (TBD in P8.1)    ─┼─>  (Phase 8)                 │                         │
                    └──────────────────────────────┼─────────────────────────┘
                                                   ▼
                    ┌──────────────── EVENT LOG (Phase 2, ours) ─────────────┐
                    │  session-xyz/                                          │
                    │    00000000.seg  00004096.seg  ...   (append-only)     │
                    │    *.idx (offset index)   *.tidx (time index)          │
                    │  append() · read(offset) · seek(ts) · tail()           │
                    └───────────┬──────────────────────────────┬─────────────┘
                                │ ordered raw stream           │ (also read by)
                                ▼                              ▼
              ┌──────────── PROCESSING (Phase 3) ───────┐   ┌─ QUALITY (Phase 7) ─┐
              │ decoders → event-time merge (watermark) │   │ detectors: frozen,  │
              │         → RaceState.apply(event)        │──>│ gaps, skew, jumps   │
              │         → snapshots every N s           │   │ injector (log→log)  │
              └───────────┬─────────────────────────────┘   └─────────┬───────────┘
                          │ state deltas + snapshots                  │ health flags
                          ▼                                           ▼
              ┌──────────── ML (Phase 9/10) ──────────────────────────────────┐
              │ features → your inference engine (ONNX, LRU, batching)        │
              │          → calibrated probs / intervals / "abstain"           │
              └───────────┬───────────────────────────────────────────────────┘
                          ▼
              ┌──────────── GATEWAY (Phase 4) ──────────┐
              │ FastAPI REST + WebSocket                │
              │ per-client cursor: live | replay@speed  │
              │ bounded queues, latest-wins positions   │
              └───────────┬─────────────────────────────┘
                          ▼  WS: snapshot, then deltas
              ┌──────────── FRONTEND (Phase 1/5) ───────┐
              │ React: SVG track, dots + interpolation, │
              │ leaderboard, driver panel, charts       │
              └─────────────────────────────────────────┘

      Observability (Phase 6): Prometheus metrics + Loki logs from every box → Grafana
```

## Principles

1. **Raw first, derive later (event sourcing).** Adapters only normalise and
   append; everything downstream is rebuilt from the log.
2. **Two timestamps.** `event_ts` (when it happened) orders processing;
   `ingest_ts` (when it arrived) measures lag and staleness.
3. **One adapter interface.** Historical and live look identical downstream.
4. **Pure processing.** `state = apply(state, event)` with no clocks, randomness
   or I/O, so replay is deterministic.
5. **Gateway decouples producer from consumers.** Per-client bounded queues;
   positions are latest-wins, discrete events are never dropped.
6. **Failures are visible, never silent.** Lag/health metrics everywhere; stale
   data is shown as stale.
