# GraphSkill

**Topology-Aware Procedural Knowledge Routing for LLM Agents**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-orange.svg)](https://docs.astral.sh/ruff/)

---

## Overview

GraphSkill is middleware for LLM Agent ecosystems that provides intelligent skill routing based on topology-aware knowledge graphs. It converts discrete `SKILL.md` files into a structured knowledge graph with dependency relationships, and dynamically routes the minimum necessary skill subset to agents at runtime.

### Key Features

- **Topology-Aware Routing**: Understands REQUIRES, CONFLICTS_WITH, ENHANCES, and SUBSTITUTES relationships
- **Conflict Resolution**: MWIS (Maximum Weight Independent Set) algorithm ensures zero-conflict output
- **Hybrid Retrieval**: Semantic vector search + graph expansion for comprehensive skill discovery
- **Self-Evolution**: EWMA reliability decay and implicit edge discovery based on telemetry data
- **Framework Integration**: Adapters for LangChain, AutoGen, and OpenDevin

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GraphSkill Architecture                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │ Ingestion   │    │ Graph-Vector│    │ Routing     │              │
│  │ Engine      │───▶│ Store       │───▶│ Gateway     │              │
│  │ (Offline)   │    │ (Storage)   │    │ (Online)    │              │
│  └─────────────┘    └─────────────┘    └─────────────┘              │
│         │                  │                  │                      │
│         ▼                  ▼                  ▼                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Telemetry & Feedback                       │   │
│  │  • EWMA Reliability Decay  • Implicit Edge Discovery          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/graphskill/graphskill.git
cd graphskill

# Install dependencies (using uv)
cd src/python
uv sync

# Or with pip
pip install -e .
```

### Basic Usage

```python
from graphskill import RoutingRequest

# Create a routing request
request = RoutingRequest(
    query="I need to commit my changes to the git repository",
    max_tokens=4096
)

# The routing gateway will return the minimum necessary skills
# with zero conflicts and proper dependency ordering
```

---

## Documentation

- [ROADMAP.md](ROADMAP.md) - Project roadmap and implementation plan
- [docs/](docs/) - RFC architecture documentation
- [plans/](plans/) - Stage-by-stage implementation plans

### RFC Documents

| Document | Description |
|----------|-------------|
| [RFC-00](docs/RFC-00-architecture-overview.md) | Architecture Overview |
| [RFC-01](docs/RFC-01-data-specification-storage-layer.md) | Data Specification & Storage |
| [RFC-02](docs/RFC-02-offline-ingestion-pipeline.md) | Ingestion Pipeline |
| [RFC-03](docs/RFC-03-online-routing-gateway.md) | Routing Gateway |
| [RFC-04](docs/RFC-04-runtime-integration-layer.md) | Runtime Integration |
| [RFC-05](docs/RFC-05-telemetry-self-evolution-feedback.md) | Telemetry & Self-Evolution |
| [RFC-06](docs/RFC-06-performance-security-high-availability.md) | Performance & Security |
| [RFC-07](docs/RFC-07-api-interface-specification.md) | API Specification |
| [RFC-08](docs/RFC-08-data-structures-schema.md) | Data Structures |
| [RFC-09](docs/RFC-09-deployment-operations.md) | Deployment & Operations |
| [RFC-10](docs/RFC-10-testing-quality-assurance.md) | Testing & QA |
| [RFC-11](docs/RFC-11-security-permission-model.md) | Security & Permissions |

---

## Development

### Setup Development Environment

```bash
# Install development dependencies
cd src/python
uv sync --extra dev --extra test

# Run tests
uv run pytest tests/ -v

# Run linting
uv run ruff check graphskill

# Run type checking
uv run mypy graphskill --strict
```

### Project Structure

```
src/python/
├── graphskill/
│   ├── core/           # Core data structures
│   ├── ingestion/      # Skill parsing and graph construction
│   ├── storage/        # Database clients
│   ├── routing/        # Routing engine
│   ├── runtime/        # Agent framework adapters
│   ├── telemetry/      # Monitoring and self-evolution
│   ├── api/            # REST/gRPC endpoints
│   └── utils/          # Utilities
├── tests/
│   ├── unit/           # Unit tests
│   ├── integration/    # Integration tests
│   ├── e2e/            # End-to-end tests
│   └── performance/    # Performance tests
└── pyproject.toml
```

---

## License

Apache License 2.0 - See [LICENSE](LICENSE) for details.

---

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

---

## Contact

- **Email**: team@graphskill.dev
- **GitHub**: https://github.com/graphskill/graphskill