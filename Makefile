.PHONY: system-tests system-tests-clean

# ==========================
# System tests
# ==========================

SYSTEM_TEST_PROJECT := impulses-test
SYSTEM_TEST_COMPOSE := docker-compose -p $(SYSTEM_TEST_PROJECT) -f system-tests/docker-compose.test.yml --env-file system-tests/.env

system-tests: ## Run system tests in isolated Docker stack (no host ports exposed). Use TESTS= to filter (e.g., make system-tests TESTS="-n 1,3,5")
	@echo "Starting isolated test stack..."
	$(SYSTEM_TEST_COMPOSE) up --build -d postgres app
	@echo "Running tester container..."
	# Run tester in attached mode so exit code propagates
	# Pass TESTS variable to docker-compose (e.g., make system-tests TESTS="-n 1-5")
	TEST_ARGS="$(TESTS)" $(SYSTEM_TEST_COMPOSE) up --build --abort-on-container-exit tester || (\
	  echo "Tests failed" && $(SYSTEM_TEST_COMPOSE) logs --no-color && $(SYSTEM_TEST_COMPOSE) down -v && exit 1 )
	@echo "Tests completed successfully. Tearing down..."
	$(SYSTEM_TEST_COMPOSE) down -v

system-tests-clean: ## Force remove test stack and volumes
	$(SYSTEM_TEST_COMPOSE) down -v || true
