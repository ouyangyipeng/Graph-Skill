"""
Unit tests for GraphSkill exceptions.

Tests for exceptions defined in graphskill/core/exceptions.py.
"""

from __future__ import annotations

import pytest

from graphskill.core.exceptions import (
    GraphSkillError,
    ValidationError,
    SchemaValidationError,
    PermissionValidationError,
    RoutingError,
    RoutingTimeoutError,
    NoSkillsFoundError,
    ConflictResolutionError,
    IngestionError,
    ParseError,
    DAGValidationError,
    TopologyInferenceError,
    DatabaseError,
    GraphDatabaseError,
    VectorDatabaseError,
    CacheError,
    DualWriteError,
    PermissionError,
    PermissionDeniedError,
    SandboxViolationError,
    ConfigurationError,
    MissingConfigurationError,
    TimeoutError,
    EmbeddingTimeoutError,
    LLMTimeoutError,
    AuthenticationError,
    TokenExpiredError,
    RateLimitError,
    get_http_status,
    ERROR_CODE_TO_HTTP_STATUS,
)


class TestGraphSkillError:
    """Tests for base GraphSkillError."""
    
    def test_create_base_error(self) -> None:
        """Test creating base error."""
        error = GraphSkillError("Test error message")
        
        assert error.message == "Test error message"
        assert error.code == "GS-0000"
        assert error.details == {}
    
    def test_create_error_with_code(self) -> None:
        """Test creating error with custom code."""
        error = GraphSkillError("Test error", code="GS-9999")
        
        assert error.code == "GS-9999"
    
    def test_create_error_with_details(self) -> None:
        """Test creating error with details."""
        error = GraphSkillError(
            "Test error",
            details={"key": "value", "count": 10}
        )
        
        assert error.details["key"] == "value"
        assert error.details["count"] == 10
    
    def test_to_dict(self) -> None:
        """Test converting error to dictionary."""
        error = GraphSkillError(
            "Test error",
            code="GS-1000",
            details={"field": "test"}
        )
        
        result = error.to_dict()
        
        assert "error" in result
        assert result["error"]["code"] == "GS-1000"
        assert result["error"]["message"] == "Test error"
        assert result["error"]["details"]["field"] == "test"


class TestValidationError:
    """Tests for ValidationError."""
    
    def test_create_validation_error(self) -> None:
        """Test creating validation error."""
        error = ValidationError("Invalid input")
        
        assert error.code == "GS-1000"
        assert error.message == "Invalid input"
    
    def test_create_validation_error_with_field(self) -> None:
        """Test creating validation error with field."""
        error = ValidationError(
            "Invalid value",
            field="uid",
            value="invalid-uid"
        )
        
        assert error.details["field"] == "uid"
        assert error.details["value"] == "invalid-uid"
    
    def test_schema_validation_error(self) -> None:
        """Test SchemaValidationError."""
        error = SchemaValidationError(
            "Schema validation failed",
            schema_path="/properties/uid"
        )
        
        assert error.code == "GS-1001"
        assert error.details["schema_path"] == "/properties/uid"
    
    def test_permission_validation_error(self) -> None:
        """Test PermissionValidationError."""
        error = PermissionValidationError(
            "Invalid permission format",
            permission="FS:read"
        )
        
        assert error.code == "GS-1002"
        assert error.details["permission"] == "FS:read"


class TestRoutingError:
    """Tests for RoutingError."""
    
    def test_create_routing_error(self) -> None:
        """Test creating routing error."""
        error = RoutingError("Routing failed")
        
        assert error.code == "GS-2000"
    
    def test_routing_error_with_request_id(self) -> None:
        """Test routing error with request ID."""
        error = RoutingError(
            "Routing failed",
            request_id="req-123"
        )
        
        assert error.details["request_id"] == "req-123"
    
    def test_routing_timeout_error(self) -> None:
        """Test RoutingTimeoutError."""
        error = RoutingTimeoutError(timeout_ms=500)
        
        assert error.code == "GS-2001"
        assert error.details["timeout_ms"] == 500
    
    def test_no_skills_found_error(self) -> None:
        """Test NoSkillsFoundError."""
        error = NoSkillsFoundError(query="test query")
        
        assert error.code == "GS-2002"
        assert error.details["query"] == "test query"
    
    def test_conflict_resolution_error(self) -> None:
        """Test ConflictResolutionError."""
        error = ConflictResolutionError(
            conflicting_skills=["skill:a", "skill:b"]
        )
        
        assert error.code == "GS-2003"
        assert error.details["conflicting_skills"] == ["skill:a", "skill:b"]


class TestIngestionError:
    """Tests for IngestionError."""
    
    def test_create_ingestion_error(self) -> None:
        """Test creating ingestion error."""
        error = IngestionError(
            "Ingestion failed",
            skill_id="test:skill",
            file_path="/skills/test/SKILL.md"
        )
        
        assert error.code == "GS-3000"
        assert error.details["skill_id"] == "test:skill"
        assert error.details["file_path"] == "/skills/test/SKILL.md"
    
    def test_parse_error(self) -> None:
        """Test ParseError."""
        error = ParseError("YAML parsing failed", line_number=10)
        
        assert error.code == "GS-3001"
        assert error.details["line_number"] == 10
    
    def test_dag_validation_error(self) -> None:
        """Test DAGValidationError."""
        error = DAGValidationError(
            cycle=["skill:a", "skill:b", "skill:a"]
        )
        
        assert error.code == "GS-3002"
        assert error.details["cycle"] == ["skill:a", "skill:b", "skill:a"]
    
    def test_topology_inference_error(self) -> None:
        """Test TopologyInferenceError."""
        error = TopologyInferenceError()
        
        assert error.code == "GS-3003"


class TestDatabaseError:
    """Tests for DatabaseError."""
    
    def test_create_database_error(self) -> None:
        """Test creating database error."""
        error = DatabaseError(
            "Connection failed",
            database="neo4j",
            operation="query"
        )
        
        assert error.code == "GS-4000"
        assert error.details["database"] == "neo4j"
        assert error.details["operation"] == "query"
    
    def test_graph_database_error(self) -> None:
        """Test GraphDatabaseError."""
        error = GraphDatabaseError(
            "Cypher query failed",
            query="MATCH (n) RETURN n"
        )
        
        assert error.code == "GS-4001"
        assert error.details["query"] == "MATCH (n) RETURN n"
    
    def test_vector_database_error(self) -> None:
        """Test VectorDatabaseError."""
        error = VectorDatabaseError(
            "Collection not found",
            collection="skill_embeddings"
        )
        
        assert error.code == "GS-4002"
        assert error.details["collection"] == "skill_embeddings"
    
    def test_cache_error(self) -> None:
        """Test CacheError."""
        error = CacheError("Cache miss", key="skill:test")
        
        assert error.code == "GS-4003"
        assert error.details["key"] == "skill:test"
    
    def test_dual_write_error(self) -> None:
        """Test DualWriteError."""
        error = DualWriteError(rollback_executed=True)
        
        assert error.code == "GS-4004"
        assert error.details["rollback_executed"] is True


class TestPermissionError:
    """Tests for PermissionError."""
    
    def test_create_permission_error(self) -> None:
        """Test creating permission error."""
        error = PermissionError(
            "Permission check failed",
            skill_id="test:skill",
            permission="fs:write"
        )
        
        assert error.code == "GS-5000"
        assert error.details["skill_id"] == "test:skill"
        assert error.details["permission"] == "fs:write"
    
    def test_permission_denied_error(self) -> None:
        """Test PermissionDeniedError."""
        error = PermissionDeniedError(
            resource="/etc/passwd",
            action="read"
        )
        
        assert error.code == "GS-5001"
        assert error.details["resource"] == "/etc/passwd"
        assert error.details["action"] == "read"
    
    def test_sandbox_violation_error(self) -> None:
        """Test SandboxViolationError."""
        error = SandboxViolationError(
            violation_type="network_access"
        )
        
        assert error.code == "GS-5002"
        assert error.details["violation_type"] == "network_access"


class TestConfigurationError:
    """Tests for ConfigurationError."""
    
    def test_create_configuration_error(self) -> None:
        """Test creating configuration error."""
        error = ConfigurationError(
            "Invalid configuration",
            config_key="neo4j.uri"
        )
        
        assert error.code == "GS-6000"
        assert error.details["config_key"] == "neo4j.uri"
    
    def test_missing_configuration_error(self) -> None:
        """Test MissingConfigurationError."""
        error = MissingConfigurationError(config_key="api.key")
        
        assert error.code == "GS-6001"
        assert error.details["config_key"] == "api.key"


class TestTimeoutError:
    """Tests for TimeoutError."""
    
    def test_create_timeout_error(self) -> None:
        """Test creating timeout error."""
        error = TimeoutError(
            "Operation timed out",
            timeout_ms=1000,
            elapsed_ms=1500
        )
        
        assert error.code == "GS-7000"
        assert error.details["timeout_ms"] == 1000
        assert error.details["elapsed_ms"] == 1500
    
    def test_embedding_timeout_error(self) -> None:
        """Test EmbeddingTimeoutError."""
        error = EmbeddingTimeoutError()
        
        assert error.code == "GS-7001"
    
    def test_llm_timeout_error(self) -> None:
        """Test LLMTimeoutError."""
        error = LLMTimeoutError(model="gpt-4")
        
        assert error.code == "GS-7002"
        assert error.details["model"] == "gpt-4"


class TestAuthenticationError:
    """Tests for AuthenticationError."""
    
    def test_create_authentication_error(self) -> None:
        """Test creating authentication error."""
        error = AuthenticationError()
        
        assert error.code == "GS-8000"
    
    def test_token_expired_error(self) -> None:
        """Test TokenExpiredError."""
        error = TokenExpiredError()
        
        assert error.code == "GS-8001"


class TestRateLimitError:
    """Tests for RateLimitError."""
    
    def test_create_rate_limit_error(self) -> None:
        """Test creating rate limit error."""
        error = RateLimitError(
            limit=100,
            retry_after=60
        )
        
        assert error.code == "GS-9000"
        assert error.details["limit"] == 100
        assert error.details["retry_after"] == 60


class TestHTTPStatusMapping:
    """Tests for HTTP status code mapping."""
    
    def test_get_http_status_validation(self) -> None:
        """Test HTTP status for validation errors."""
        assert get_http_status("GS-1000") == 400
        assert get_http_status("GS-1001") == 400
        assert get_http_status("GS-1002") == 400
    
    def test_get_http_status_routing(self) -> None:
        """Test HTTP status for routing errors."""
        assert get_http_status("GS-2000") == 500
        assert get_http_status("GS-2001") == 504  # Gateway Timeout
        assert get_http_status("GS-2002") == 404  # Not Found
        assert get_http_status("GS-2003") == 500
    
    def test_get_http_status_database(self) -> None:
        """Test HTTP status for database errors."""
        assert get_http_status("GS-4000") == 503
        assert get_http_status("GS-4001") == 503
        assert get_http_status("GS-4002") == 503
    
    def test_get_http_status_permission(self) -> None:
        """Test HTTP status for permission errors."""
        assert get_http_status("GS-5000") == 403
        assert get_http_status("GS-5001") == 403
        assert get_http_status("GS-5002") == 403
    
    def test_get_http_status_timeout(self) -> None:
        """Test HTTP status for timeout errors."""
        assert get_http_status("GS-7000") == 504
        assert get_http_status("GS-7001") == 504
        assert get_http_status("GS-7002") == 504
    
    def test_get_http_status_authentication(self) -> None:
        """Test HTTP status for authentication errors."""
        assert get_http_status("GS-8000") == 401
        assert get_http_status("GS-8001") == 401
    
    def test_get_http_status_rate_limit(self) -> None:
        """Test HTTP status for rate limit errors."""
        assert get_http_status("GS-9000") == 429
    
    def test_get_http_status_unknown(self) -> None:
        """Test HTTP status for unknown error codes."""
        assert get_http_status("GS-9999") == 500
        assert get_http_status("UNKNOWN") == 500
    
    def test_error_code_to_http_status_complete(self) -> None:
        """Test all error codes have HTTP status mapping."""
        # Verify all defined error codes have mappings
        for code in ERROR_CODE_TO_HTTP_STATUS:
            status = get_http_status(code)
            assert status >= 400
            assert status < 600