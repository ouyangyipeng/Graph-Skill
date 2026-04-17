"""
GraphSkill constants and configuration defaults.

This module defines all constants and default values for the GraphSkill system.
"""

from __future__ import annotations


# ============================================
# Routing Defaults
# ============================================

DEFAULT_MAX_TOKENS: int = 4096
"""Default maximum token budget for routing response."""

DEFAULT_TOP_K: int = 5
"""Default number of seed skills to retrieve from vector search (VR baseline top-5)."""

DEFAULT_EXPANSION_DEPTH: int = 1
"""Default graph expansion depth (1-hop, VR-first architecture)."""

DEFAULT_SIMILARITY_THRESHOLD: float = 0.5
"""Default minimum similarity threshold for vector search."""

DEFAULT_MIN_RELIABILITY: float = 0.5
"""Default minimum reliability threshold for skill selection."""

MIN_RELIABILITY_THRESHOLD: float = 0.5
"""Minimum reliability threshold for skill selection."""

# ============================================
# Scoring Weights
# ============================================

DEFAULT_ALPHA: float = 0.8
"""Default weight for similarity score in composite scoring (VR-first: similarity dominant)."""

DEFAULT_BETA: float = 0.1
"""Default weight for PageRank score in composite scoring (VR-first: reduced structural weight)."""

DEFAULT_GAMMA: float = 0.1
"""Default weight for reliability score in composite scoring (VR-first: reduced reliability weight)."""

# ============================================
# EWMA Decay Parameters
# ============================================

EWMA_ALPHA: float = 0.7
"""EWMA decay factor for reliability calculation."""

EWMA_MIN_OBSERVATIONS: int = 5
"""Minimum observations before applying EWMA formula."""

EWMA_DECAY_PERIOD_HOURS: int = 24
"""Time period for reliability decay when no observations."""

EWMA_COLD_START_RATE: float = 1.0
"""Default success rate for cold-start skills."""

# ============================================
# Cache Configuration
# ============================================

CACHE_TTL_SECONDS: int = 300
"""Default cache TTL in seconds (5 minutes)."""

CACHE_MAX_SIZE: int = 10000
"""Maximum number of entries in cache."""

EMBEDDING_CACHE_TTL_SECONDS: int = 3600
"""Embedding cache TTL in seconds (1 hour)."""

# ============================================
# Performance Targets
# ============================================

ROUTING_LATENCY_P50_TARGET_MS: int = 100
"""Target P50 routing latency in milliseconds."""

ROUTING_LATENCY_P99_TARGET_MS: int = 500
"""Target P99 routing latency in milliseconds."""

ROUTING_THROUGHPUT_TARGET_QPS: int = 1000
"""Target throughput in queries per second."""

VECTOR_SEARCH_TIMEOUT_MS: int = 50
"""Vector search timeout in milliseconds."""

GRAPH_EXPANSION_TIMEOUT_MS: int = 50
"""Graph expansion timeout in milliseconds."""

# ============================================
# Database Configuration
# ============================================

NEO4J_DEFAULT_URI: str = "bolt://localhost:7687"
"""Default Neo4j connection URI."""

NEO4J_DEFAULT_USER: str = "neo4j"
"""Default Neo4j username."""

NEO4J_DEFAULT_PASSWORD: str = "password"
"""Default Neo4j password."""

NEO4J_MAX_CONNECTION_POOL_SIZE: int = 50
"""Maximum Neo4j connection pool size."""

MILVUS_DEFAULT_HOST: str = "localhost"
"""Default Milvus host."""

MILVUS_DEFAULT_PORT: int = 19530
"""Default Milvus port."""

MILVUS_COLLECTION_NAME: str = "skill_embeddings"
"""Default Milvus collection name."""

MILVUS_DIMENSION: int = 1536
"""Default embedding dimension (OpenAI text-embedding-3-small)."""

MILVUS_VECTOR_DIMENSION: int = 1536
"""Alias for MILVUS_DIMENSION, for backward compatibility."""

MILVUS_HNSW_M: int = 16
"""HNSW index M parameter."""

MILVUS_HNSW_EF_CONSTRUCTION: int = 200
"""HNSW index efConstruction parameter."""

MILVUS_INDEX_TYPE: str = "HNSW"
"""Default Milvus index type."""

MILVUS_METRIC_TYPE: str = "COSINE"
"""Default Milvus metric type for distance calculation."""

REDIS_DEFAULT_HOST: str = "localhost"
"""Default Redis host."""

REDIS_DEFAULT_PORT: int = 6379
"""Default Redis port."""

REDIS_DEFAULT_DB: int = 0
"""Default Redis database number."""

# ============================================
# Kafka Configuration
# ============================================

KAFKA_DEFAULT_BOOTSTRAP_SERVERS: str = "localhost:9092"
"""Default Kafka bootstrap servers."""

KAFKA_TOPIC_SKILL_EXECUTION: str = "graphskill.skill.execution"
"""Kafka topic for skill execution events."""

KAFKA_TOPIC_SKILL_CO_OCCURRENCE: str = "graphskill.skill.co_occurrence"
"""Kafka topic for skill co-occurrence events."""

KAFKA_TOPIC_SKILL_CONFLICT: str = "graphskill.skill.conflict"
"""Kafka topic for skill conflict events."""

KAFKA_CONSUMER_GROUP: str = "graphskill-telemetry"
"""Default Kafka consumer group."""

# ============================================
# Ingestion Configuration
# ============================================

SKILL_FILE_NAME: str = "SKILL.md"
"""Standard skill file name."""

SKILL_DIR_ENV_VAR: str = "SKILL_DIR"
"""Environment variable for skill directory path."""

DEFAULT_SKILL_DIR: str = "/skills"
"""Default skill directory path."""

BATCH_IMPORT_SIZE: int = 100
"""Batch size for skill import."""

INGESTION_TIMEOUT_SECONDS: int = 300
"""Timeout for skill ingestion in seconds."""

# ============================================
# LLM Configuration
# ============================================

DEFAULT_LLM_MODEL: str = "gpt-4-turbo-preview"
"""Default LLM model for topology inference."""

DEFAULT_EMBEDDING_MODEL: str = "text-embedding-3-small"
"""Default embedding model."""

LLM_MAX_TOKENS: int = 4096
"""Maximum tokens for LLM response."""

LLM_TEMPERATURE: float = 0.3
"""Default LLM temperature for topology inference."""

# ============================================
# Permission Configuration
# ============================================

PERMISSION_PATTERN: str = r"^[a-z]+:[a-z]+(:[a-zA-Z0-9_/-]+)?$"
"""Regex pattern for permission format validation."""

PERMISSION_CACHE_TTL_SECONDS: int = 300
"""Permission cache TTL in seconds."""

# ============================================
# Sandbox Configuration
# ============================================

SANDBOX_DEFAULT_CPU_LIMIT: str = "500m"
"""Default CPU limit for sandbox."""

SANDBOX_DEFAULT_MEMORY_LIMIT: str = "512Mi"
"""Default memory limit for sandbox."""

SANDBOX_DEFAULT_DISK_LIMIT: str = "1Gi"
"""Default disk limit for sandbox."""

SANDBOX_DEFAULT_TIMEOUT_SECONDS: int = 300
"""Default sandbox execution timeout."""

# ============================================
# Telemetry Configuration
# ============================================

TELEMETRY_MIN_CO_OCCURRENCE_COUNT: int = 10
"""Minimum co-occurrence count for implicit edge discovery."""

TELEMETRY_MIN_CO_OCCURRENCE_RATE: float = 0.3
"""Minimum co-occurrence rate for implicit edge discovery."""

TELEMETRY_CONFIDENCE_THRESHOLD: float = 0.7
"""Confidence threshold for implicit edge creation."""

TELEMETRY_ANALYSIS_WINDOW_DAYS: int = 30
"""Analysis window for co-occurrence analysis."""

# ============================================
# API Configuration
# ============================================

API_DEFAULT_PORT: int = 8080
"""Default API server port."""

API_DEFAULT_HOST: str = "0.0.0.0"
"""Default API server host."""

API_RATE_LIMIT_PER_MINUTE: int = 60
"""Default rate limit per minute."""

API_RATE_LIMIT_BURST: int = 10
"""Default rate limit burst."""

# ============================================
# Logging Configuration
# ============================================

LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
"""Default log format."""

LOG_LEVEL: str = "INFO"
"""Default log level."""

LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
"""Default log date format."""

# ============================================
# Version Information
# ============================================

SCHEMA_VERSION: str = "1.0.0"
"""Current schema version."""

API_VERSION: str = "v1"
"""Current API version."""

# ============================================
# Edge Type Priorities (for conflict resolution)
# ============================================

EDGE_TYPE_PRIORITY: dict[str, int] = {
    "REQUIRES": 1,        # Highest priority - must satisfy
    "CONFLICTS_WITH": 2,  # High priority - must avoid
    "ENHANCES": 3,        # Medium priority - optional
    "SUBSTITUTES": 4,     # Low priority - alternatives
}
"""Priority order for edge types in conflict resolution."""

# ============================================
# Error Messages
# ============================================

ERROR_MSG_SKILL_NOT_FOUND: str = "Skill not found"
ERROR_MSG_PERMISSION_DENIED: str = "Permission denied"
ERROR_MSG_ROUTING_TIMEOUT: str = "Routing operation timed out"
ERROR_MSG_DAG_CYCLE: str = "Dependency graph contains cycles"
ERROR_MSG_DUAL_WRITE_FAILED: str = "Dual-write transaction failed"
ERROR_MSG_INVALID_PERMISSION_FORMAT: str = "Invalid permission format"
ERROR_MSG_SELF_EDGE: str = "Self-referential edges are not allowed"