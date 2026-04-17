# GraphSkill Makefile
# Build, test, and development commands

.PHONY: help install dev test lint format clean build docker docs

# ============================================
# Default target
# ============================================

help:
	@echo "GraphSkill Makefile Commands:"
	@echo ""
	@echo "  install        Install production dependencies"
	@echo "  dev            Install development dependencies"
	@echo "  test           Run all tests"
	@echo "  test-unit      Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-cov       Run tests with coverage report"
	@echo "  lint           Run linting (ruff)"
	@echo "  format         Format code (black/ruff)"
	@echo "  typecheck      Run type checking (mypy)"
	@echo "  clean          Clean build artifacts"
	@echo "  build          Build package"
	@echo "  docker         Build Docker image"
	@echo "  docker-compose Start local development environment"
	@echo "  docs           Build documentation"
	@echo "  db-init        Initialize databases"
	@echo "  run            Run development server"
	@echo ""

# ============================================
# Installation
# ============================================

install:
	cd src/python && uv sync

dev:
	cd src/python && uv sync --extra dev --extra test

# ============================================
# Testing
# ============================================

test:
	cd src/python && uv run pytest tests/ -v

test-unit:
	cd src/python && uv run pytest tests/unit -v -m unit

test-integration:
	cd src/python && uv run pytest tests/integration -v -m integration

test-e2e:
	cd src/python && uv run pytest tests/e2e -v -m e2e

test-cov:
	cd src/python && uv run pytest tests/ -v --cov=graphskill --cov-report=html --cov-report=term

test-performance:
	cd src/python && uv run pytest tests/performance -v -m performance

# ============================================
# Code Quality
# ============================================

lint:
	cd src/python && uv run ruff check graphskill tests

format:
	cd src/python && uv run ruff format graphskill tests
	cd src/python && uv run black graphskill tests

format-check:
	cd src/python && uv run ruff format --check graphskill tests
	cd src/python && uv run black --check graphskill tests

typecheck:
	cd src/python && uv run mypy graphskill --strict

security:
	cd src/python && uv run bandit -r graphskill -ll

# ============================================
# Build & Clean
# ============================================

clean:
	rm -rf src/python/build/
	rm -rf src/python/dist/
	rm -rf src/python/*.egg-info
	rm -rf src/python/.pytest_cache
	rm -rf src/python/.mypy_cache
	rm -rf src/python/.ruff_cache
	rm -rf src/python/htmlcov
	rm -rf src/python/.coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build:
	cd src/python && uv build

# ============================================
# Docker
# ============================================

docker:
	docker build -f deploy/docker/Dockerfile.python -t graphskill:latest .

docker-compose:
	docker-compose -f deploy/docker/docker-compose.dev.yaml up -d

docker-down:
	docker-compose -f deploy/docker/docker-compose.dev.yaml down

docker-logs:
	docker-compose -f deploy/docker/docker-compose.dev.yaml logs -f

# ============================================
# Database
# ============================================

db-init-neo4j:
	cypher-shell -u neo4j -p ${NEO4J_PASSWORD} -f scripts/db/neo4j_init.cypher

db-init-milvus:
	python scripts/db/milvus_init.py --host ${MILVUS_HOST} --port ${MILVUS_PORT}

db-init: db-init-neo4j db-init-milvus

# ============================================
# Documentation
# ============================================

docs:
	cd src/python && uv run mkdocs serve

docs-build:
	cd src/python && uv run mkdocs build

# ============================================
# Development Server
# ============================================

run:
	cd src/python && uv run python -m graphskill.api.rest

run-dev:
	cd src/python && uv run uvicorn graphskill.api.rest:app --reload --host 0.0.0.0 --port 8080

# ============================================
# Pre-commit
# ============================================

pre-commit:
	cd src/python && uv run pre-commit run --all-files

# ============================================
# All checks
# ============================================

check: lint format-check typecheck test-unit
	@echo "All checks passed!"