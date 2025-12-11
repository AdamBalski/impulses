# System Tests

End-to-end integration tests for Impulses using Docker Compose.

## Structure

```
system-tests/
├── README.md                        # This file
├── docker-compose.test.yml          # Isolated test stack definition
├── run_all.py                       # Test runner (executes all or chosen scenarios)
├── utils.py                         # Common test utilities
└── scenarios/                       # Test scenario implementations (each test in separate python file)
```

# Run tests
```bash
# Run all scenarios
./run.sh

# Run specific scenarios by number
./run.sh TESTS="-n 1"              # Run only scenario 1
./run.sh TESTS="-n 1,3,5"          # Run scenarios 1, 3, and 5
./run.sh TESTS="-n 1-5"            # Run scenarios 1 through 5
./run.sh TESTS="-n 1-5,15-18"      # Run scenarios 1-5 and 15-18

# Run scenarios by pattern
./run.sh TESTS="-p '*sdk*'"        # Run SDK-related scenarios
./run.sh TESTS="-p '*auth*'"       # Run auth-related scenarios

# List available scenarios
./run.sh TESTS="-l"
```