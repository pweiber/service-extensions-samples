# Basic Extreme Load Test Results - Run 1

**Date:** 2026-01-15
**Test Mode:** extreme (600s duration, 2000 VUs, 60s warmup)
**Workload:** Basic header manipulation (I/O-bound, lightweight)
**Resources:** 4 CPU cores, 2GB memory per container

## Summary Table

| Rank | SDK             | RPS    | Success Rate | P50 Latency | P99 Latency | Report                                                                                                                                             |
|------|-----------------|--------|--------------|-------------|-------------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| 1    | **Go**          | 52,837 | 99.99%       | 35.3ms      | 61ms        | [Report](01_basic_extreme/go_basic_extreme_default_20260115_164843/go_basic_extreme_default_20260115_164843_load_test_report.md)                   |
| 2    | **Java**        | 52,597 | 99.99%       | 35.5ms      | 56ms        | [Report](01_basic_extreme/java_basic_extreme_default_20260115_170033/java_basic_extreme_default_20260115_170033_load_test_report.md)               |
| 3    | **Rust**        | 49,720 | 99.99%       | 37.6ms      | 63ms        | [Report](01_basic_extreme/rust_basic_extreme_default_20260115_163643/rust_basic_extreme_default_20260115_163643_load_test_report.md)               |
| 4    | **C++ Sync**    | 3,571  | 99.94%       | 558ms       | 623ms       | [Report](01_basic_extreme/cpp_basic_extreme_default_20260115_172421/cpp_basic_extreme_default_20260115_172421_load_test_report.md)                 |
| 5    | **Python Base** | 1,542  | 99.80%       | 1,296ms     | 1,362ms     | [Report](01_basic_extreme/python_base_basic_extreme_default_20260115_160053/python_base_basic_extreme_default_20260115_160053_load_test_report.md) |
| 6    | **Python MP**   | 1,523  | 99.80%       | 1,312ms     | 1,377ms     | [Report](01_basic_extreme/python_mp_basic_extreme_default_20260115_162444/python_mp_basic_extreme_default_20260115_162444_load_test_report.md)     |
| 7    | **Python 8T**   | 1,221  | 99.75%       | 1,638ms     | 1,727ms     | [Report](01_basic_extreme/python_8t_basic_extreme_default_20260115_161252/python_8t_basic_extreme_default_20260115_161252_load_test_report.md)     |
