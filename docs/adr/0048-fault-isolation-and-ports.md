# ADR-0048: Ports & adapters with fault isolation

- Status: Accepted
- Date: 2026-10-28

## Decision
Every sensor, score module, model, TTS engine and store sits behind a versioned port registered in `oiris/registry.py` (built-ins + the `oiris.plugins` entry-point group). Core (`engine.py`, `bus.py`, `fusion/`) never imports a concrete driver. Each adapter thread is wrapped with an exception guard, a read-timeout watchdog, restart with exponential back-off and a circuit breaker; a failing module is marked FAILED and fusion masks its family. Score modules run through `safe_update`; model loads fall back to last-good or disabled. Startup config is validated with safe defaults and per-module feature flags (security and the bus cannot be disabled).

## Consequences
A plugin can crash, hang or emit garbage without taking down the process (tests/test_fault_injection.py). Port major-version mismatches are rejected at registration.
