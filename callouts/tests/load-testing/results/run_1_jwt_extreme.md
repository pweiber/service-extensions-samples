# JWT Extreme Load Test Results - Run 1

**Date:** 2026-01-13
**Test Mode:** extreme (600s duration, 2000 VUs, 60s warmup)
**Workload:** JWT RS256 validation (CPU-intensive)
**Resources:** 4 CPU cores, 2GB memory per container

## Summary Table

| Rank | SDK             | RPS    | Success Rate | P50 Latency | P99 Latency | Report                                                                                                                                                 |
|------|-----------------|--------|--------------|-------------|-------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1    | **Rust**        | 38,053 | 99.99%       | 46.3ms      | 83ms        | [Report](01_jwt_extreme/rust_jwt_extreme_default_20260113_190940/rust_jwt_extreme_default_20260113_190940_load_test_report.md)                         |
| 2    | **Go**          | 36,204 | 99.99%       | 50.3ms      | 89ms        | [Report](01_jwt_extreme/go_jwt_extreme_default_20260113_192126/go_jwt_extreme_default_20260113_192126_load_test_report.md)                             |
| 3    | **Java**        | 9,632  | 99.97%       | 204.1ms     | 261ms       | [Report](01_jwt_extreme/java_jwt_extreme_default_20260113_193304/java_jwt_extreme_default_20260113_193304_load_test_report.md)                         |
| 4    | **C++ Sync**    | 4,038  | 99.92%       | 434.6ms     | 674ms       | [Report](01_jwt_extreme/cpp_jwt_extreme_default_20260113_195632/cpp_jwt_extreme_default_20260113_195632_load_test_report.md)                           |
| 5    | **Python Base** | 1,165  | 99.71%       | 1,714ms     | 1,812ms     | [Report](01_jwt_extreme/python_baseline_jwt_extreme_default_20260113_201958/python_baseline_jwt_extreme_default_20260113_201958_load_test_report.md)   |
| 6    | **Python MP**   | 1,160  | 99.71%       | 1,724ms     | 1,796ms     | [Report](01_jwt_extreme/python_multiproc_jwt_extreme_default_20260113_204313/python_multiproc_jwt_extreme_default_20260113_204313_load_test_report.md) |
| 7    | **Python 8T**   | 927    | 99.64%       | 2,167ms     | 2,263ms     | [Report](01_jwt_extreme/python_8threads_jwt_extreme_default_20260113_203138/python_8threads_jwt_extreme_default_20260113_203138_load_test_report.md)   |
