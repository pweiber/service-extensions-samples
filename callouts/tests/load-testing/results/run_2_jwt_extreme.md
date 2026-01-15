# JWT Extreme Load Test Results - Run 2

**Date:** 2026-01-15
**Test Mode:** extreme (600s duration, 2000 VUs, 60s warmup)
**Workload:** JWT RS256 validation (CPU-intensive)
**Resources:** 4 CPU cores, 2GB memory per container

## Summary Table

| Rank | SDK             | RPS    | Success Rate | P50 Latency | P99 Latency | Report                                                                                                                                       |
|------|-----------------|--------|--------------|-------------|-------------|----------------------------------------------------------------------------------------------------------------------------------------------|
| 1    | **Rust**        | 27,784 | 99.99%       | 62.5ms      | 110ms       | [Report](02_jwt_extreme/rust_jwt_extreme_default_20260115_135958/rust_jwt_extreme_default_20260115_135958_load_test_report.md)               |
| 2    | **Go**          | 25,307 | 99.99%       | 71.6ms      | 140ms       | [Report](02_jwt_extreme/go_jwt_extreme_default_20260115_141211/go_jwt_extreme_default_20260115_141211_load_test_report.md)                   |
| 3    | **Java**        | 7,483  | 99.96%       | 267ms       | 327ms       | [Report](02_jwt_extreme/java_jwt_extreme_default_20260115_142413/java_jwt_extreme_default_20260115_142413_load_test_report.md)               |
| 4    | **C++ Sync**    | 3,103  | 99.89%       | 633ms       | 900ms       | [Report](02_jwt_extreme/cpp_jwt_extreme_default_20260115_144823/cpp_jwt_extreme_default_20260115_144823_load_test_report.md)                 |
| 5    | **Python Base** | 1,109  | 99.70%       | 1,798ms     | 1,952ms     | [Report](02_jwt_extreme/python_base_jwt_extreme_default_20260115_153710/python_base_jwt_extreme_default_20260115_153710_load_test_report.md) |
| 6    | **Python MP**   | 990    | 99.66%       | 2,014ms     | 2,312ms     | [Report](02_jwt_extreme/python_mp_jwt_extreme_default_20260115_134749/python_mp_jwt_extreme_default_20260115_134749_load_test_report.md)     |
| 7    | **Python 8T**   | 864    | 99.61%       | 2,316ms     | 2,561ms     | [Report](02_jwt_extreme/python_8t_jwt_extreme_default_20260115_133553/python_8t_jwt_extreme_default_20260115_133553_load_test_report.md)     |
