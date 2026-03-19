# Deferred Items - Phase 13

## Pre-existing Test Failure

- **File:** tests/test_connection.py::TestPollLoopReconnection::test_power_limit_restored_after_reconnect
- **Issue:** `control_state.wmaxlimpct_float` returns 7500 instead of expected 75.0 (raw vs scaled value mismatch)
- **Scope:** Unrelated to Phase 13 changes, pre-existing before this phase
