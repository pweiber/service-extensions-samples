# SDK Performance Test Commands

## Build Docker Images

```bash
# Rust
docker build -t rust-basic-callout:local -f Dockerfile.rust.basic ../../rust
docker build -t rust-jwt-callout:local -f Dockerfile.rust.jwt ../../rust

# Go
docker build -t go-basic-callout:local -f Dockerfile.go.basic ../../go
docker build -t go-jwt-callout:local -f Dockerfile.go.jwt ../../go

# Java 
docker build -t java-basic-callout:local -f Dockerfile.java.basic ../../java
docker build -t java-jwt-callout:local -f Dockerfile.java.jwt ../../java

# C++ 
docker build -t cpp-basic-callout:local -f Dockerfile.cpp.basic ../../cpp
docker build -t cpp-jwt-callout:local -f Dockerfile.cpp.jwt ../../cpp

# Python baseline (2 threads)
docker build -t python-base-basic-callout:local -f Dockerfile.python.basic ../../python-base
docker build -t python-base-jwt-callout:local -f Dockerfile.python-base.jwt ../../python-base

# Python 8 threads
docker build -t python-8t-basic-callout:local -f Dockerfile.python-8t.basic ../../python-8t
docker build -t python-8t-jwt-callout:local -f Dockerfile.python-8t.jwt ../../python-8t

# Python multiprocessing
docker build -t python-mp-basic-callout:local -f Dockerfile.python-mp.basic ../../python-mp
docker build -t python-mp-jwt-callout:local -f Dockerfile.python-mp.jwt ../../python-mp
```

## Start Test Environment

```bash
docker compose up -d
```

## Run Tests (from inside container)

```bash
# Enter container
docker compose exec load-tester bash

# Run individual tests (extreme mode: 600s, 2000 VUs)
./run-test.sh -s rust_basic -m extreme
./run-test.sh -s rust_jwt -m extreme
./run-test.sh -s go_basic -m extreme
./run-test.sh -s go_jwt -m extreme
./run-test.sh -s java_basic -m extreme
./run-test.sh -s java_jwt -m extreme
./run-test.sh -s cpp_basic -m extreme
./run-test.sh -s cpp_jwt -m extreme
./run-test.sh -s python_base_basic -m extreme
./run-test.sh -s python_base_jwt -m extreme
./run-test.sh -s python_8t_basic -m extreme
./run-test.sh -s python_8t_jwt -m extreme
./run-test.sh -s python_mp_basic -m extreme
./run-test.sh -s python_mp_jwt -m extreme
```

## Results

Results are saved to `./results/<service>_<mode>_<scenario>_<timestamp>/`
