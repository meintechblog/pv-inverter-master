# Phase 23: Deferred Items

## Pre-existing Test Failures (SF=0 Migration)

Multiple test files contain raw WMaxLimPct values designed for SF=-2 (e.g., raw 5000 = 50%, raw 7500 = 75%) but WMAXLIMPCT_SF was changed to 0, making these values invalid (5000% > 100%).

Fixed in test_proxy.py during 23-02 (directly affected files). Remaining:

- `tests/test_connection.py::TestPollLoopReconnection::test_power_limit_restored_after_reconnect` -- raw 7500 should be 75
- `tests/test_solaredge_write.py` -- multiple tests with old SF=-2 raw values
- `tests/test_webapp.py::test_power_limit_venus_override_rejection` -- likely SF mismatch
