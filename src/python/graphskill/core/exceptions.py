"""
GraphSkill exception hierarchy.

This module defines all exceptions for the GraphSkill system,
following RFC-07 API Interface Specification error code definitions.
"""

from __future__ import annotations

from typing import Optional, Any


class GraphSkillError(Exception):
    """
    Base exception for all GraphSkill errors.
    
    All GraphSkill exceptions inherit from this base class,
    providing a consistent error interface.
    
    Attributes:
        message: Error message
        code: Error code (following RFC-07 definitions)
        details: Additional error details
    """
    
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or "GS-0000"
        self.details = details or {}
    
    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API response."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class ValidationError(GraphSkillError):
    """
    Validation error.
    
    Raised when input data fails validation.
    
    Error code range: GS-1000 - GS-1999
    """
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if field:
            details["field"] = field
        if value:
            details["value"] = str(value)
        super().__init__(message, code="GS-1000", details=details)


class SchemaValidationError(ValidationError):
    """Schema validation error (GS-1001)."""
    
    def __init__(
        self,
        message: str,
        schema_path: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if schema_path:
            details["schema_path"] = schema_path
        super().__init__(message, details=details)
        self.code = "GS-1001"


class PermissionValidationError(ValidationError):
    """Permission validation error (GS-1002)."""
    
    def __init__(
        self,
        message: str,
        permission: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if permission:
            details["permission"] = permission
        super().__init__(message, details=details)
        self.code = "GS-1002"


class RoutingError(GraphSkillError):
    """
    Routing error.
    
    Raised when routing operation fails.
    
    Error code range: GS-2000 - GS-2999
    """
    
    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if request_id:
            details["request_id"] = request_id
        super().__init__(message, code="GS-2000", details=details)


class RoutingTimeoutError(RoutingError):
    """Routing timeout error (GS-2001)."""
    
    def __init__(
        self,
        message: str = "Routing operation timed out",
        timeout_ms: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if timeout_ms:
            details["timeout_ms"] = timeout_ms
        super().__init__(message, details=details)
        self.code = "GS-2001"


class NoSkillsFoundError(RoutingError):
    """No skills found error (GS-2002)."""
    
    def __init__(
        self,
        message: str = "No skills found matching the query",
        query: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if query:
            details["query"] = query
        super().__init__(message, details=details)
        self.code = "GS-2002"


class ConflictResolutionError(RoutingError):
    """Conflict resolution error (GS-2003)."""
    
    def __init__(
        self,
        message: str = "Unable to resolve skill conflicts",
        conflicting_skills: Optional[list[str]] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if conflicting_skills:
            details["conflicting_skills"] = conflicting_skills
        super().__init__(message, details=details)
        self.code = "GS-2003"


class IngestionError(GraphSkillError):
    """
    Ingestion error.
    
    Raised when skill ingestion fails.
    
    Error code range: GS-3000 - GS-3999
    """
    
    def __init__(
        self,
        message: str,
        skill_id: Optional[str] = None,
        file_path: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if skill_id:
            details["skill_id"] = skill_id
        if file_path:
            details["file_path"] = file_path
        super().__init__(message, code="GS-3000", details=details)


class ParseError(IngestionError):
    """Parse error (GS-3001)."""
    
    def __init__(
        self,
        message: str,
        line_number: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if line_number:
            details["line_number"] = line_number
        super().__init__(message, details=details)
        self.code = "GS-3001"


class DAGValidationError(IngestionError):
    """DAG validation error (GS-3002)."""
    
    def __init__(
        self,
        message: str = "Dependency graph contains cycles",
        cycle: Optional[list[str]] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if cycle:
            details["cycle"] = cycle
        super().__init__(message, details=details)
        self.code = "GS-3002"


class TopologyInferenceError(IngestionError):
    """Topology inference error (GS-3003)."""
    
    def __init__(
        self,
        message: str = "Failed to infer topology relationships",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, details=details)
        self.code = "GS-3003"


class DatabaseError(GraphSkillError):
    """
    Database error.
    
    Raised when database operation fails.
    
    Error code range: GS-4000 - GS-4999
    """
    
    def __init__(
        self,
        message: str,
        database: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if database:
            details["database"] = database
        if operation:
            details["operation"] = operation
        super().__init__(message, code="GS-4000", details=details)


class GraphDatabaseError(DatabaseError):
    """Graph database error (GS-4001)."""
    
    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if query:
            details["query"] = query
        super().__init__(message, database="neo4j", details=details)
        self.code = "GS-4001"


class VectorDatabaseError(DatabaseError):
    """Vector database error (GS-4002)."""
    
    def __init__(
        self,
        message: str,
        collection: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if collection:
            details["collection"] = collection
        super().__init__(message, database="milvus", details=details)
        self.code = "GS-4002"


class CacheError(DatabaseError):
    """Cache error (GS-4003)."""
    
    def __init__(
        self,
        message: str,
        key: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if key:
            details["key"] = key
        super().__init__(message, database="redis", details=details)
        self.code = "GS-4003"


class DualWriteError(DatabaseError):
    """Dual-write consistency error (GS-4004)."""
    
    def __init__(
        self,
        message: str = "Dual-write transaction failed",
        rollback_executed: Optional[bool] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if rollback_executed:
            details["rollback_executed"] = rollback_executed
        super().__init__(message, details=details)
        self.code = "GS-4004"


class PermissionError(GraphSkillError):
    """
    Permission error.
    
    Raised when permission check fails.
    
    Error code range: GS-5000 - GS-5999
    """
    
    def __init__(
        self,
        message: str,
        skill_id: Optional[str] = None,
        permission: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if skill_id:
            details["skill_id"] = skill_id
        if permission:
            details["permission"] = permission
        super().__init__(message, code="GS-5000", details=details)


class PermissionDeniedError(PermissionError):
    """Permission denied error (GS-5001)."""
    
    def __init__(
        self,
        message: str = "Permission denied",
        resource: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if resource:
            details["resource"] = resource
        if action:
            details["action"] = action
        super().__init__(message, details=details)
        self.code = "GS-5001"


class SandboxViolationError(PermissionError):
    """Sandbox violation error (GS-5002)."""
    
    def __init__(
        self,
        message: str = "Sandbox security violation",
        violation_type: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if violation_type:
            details["violation_type"] = violation_type
        super().__init__(message, details=details)
        self.code = "GS-5002"


class ConfigurationError(GraphSkillError):
    """
    Configuration error.
    
    Raised when configuration is invalid or missing.
    
    Error code range: GS-6000 - GS-6999
    """
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if config_key:
            details["config_key"] = config_key
        super().__init__(message, code="GS-6000", details=details)


class MissingConfigurationError(ConfigurationError):
    """Missing configuration error (GS-6001)."""
    
    def __init__(
        self,
        message: str = "Required configuration missing",
        config_key: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, config_key=config_key, details=details)
        self.code = "GS-6001"


class TimeoutError(GraphSkillError):
    """
    Timeout error.
    
    Raised when operation exceeds timeout limit.
    
    Error code range: GS-7000 - GS-7999
    """
    
    def __init__(
        self,
        message: str,
        timeout_ms: Optional[int] = None,
        elapsed_ms: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if timeout_ms:
            details["timeout_ms"] = timeout_ms
        if elapsed_ms:
            details["elapsed_ms"] = elapsed_ms
        super().__init__(message, code="GS-7000", details=details)


class EmbeddingTimeoutError(TimeoutError):
    """Embedding generation timeout error (GS-7001)."""
    
    def __init__(
        self,
        message: str = "Embedding generation timed out",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, details=details)
        self.code = "GS-7001"


class LLMTimeoutError(TimeoutError):
    """LLM inference timeout error (GS-7002)."""
    
    def __init__(
        self,
        message: str = "LLM inference timed out",
        model: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if model:
            details["model"] = model
        super().__init__(message, details=details)
        self.code = "GS-7002"


class AuthenticationError(GraphSkillError):
    """
    Authentication error.
    
    Raised when authentication fails.
    
    Error code range: GS-8000 - GS-8999
    """
    
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, code="GS-8000", details=details)


class TokenExpiredError(AuthenticationError):
    """Token expired error (GS-8001)."""
    
    def __init__(
        self,
        message: str = "Authentication token expired",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, details=details)
        self.code = "GS-8001"


class RateLimitError(GraphSkillError):
    """
    Rate limit error.
    
    Raised when rate limit is exceeded.
    
    Error code range: GS-9000 - GS-9999
    """
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        retry_after: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = details or {}
        if limit:
            details["limit"] = limit
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, code="GS-9000", details=details)


# Error code mapping for HTTP status codes
ERROR_CODE_TO_HTTP_STATUS: dict[str, int] = {
    # Validation errors (1000-1999) -> 400 Bad Request
    "GS-1000": 400,
    "GS-1001": 400,
    "GS-1002": 400,
    # Routing errors (2000-2999) -> 500 Internal Server Error
    "GS-2000": 500,
    "GS-2001": 504,  # Gateway Timeout
    "GS-2002": 404,  # Not Found
    "GS-2003": 500,
    # Ingestion errors (3000-3999) -> 400 Bad Request
    "GS-3000": 400,
    "GS-3001": 400,
    "GS-3002": 400,
    "GS-3003": 500,
    # Database errors (4000-4999) -> 503 Service Unavailable
    "GS-4000": 503,
    "GS-4001": 503,
    "GS-4002": 503,
    "GS-4003": 503,
    "GS-4004": 500,
    # Permission errors (5000-5999) -> 403 Forbidden
    "GS-5000": 403,
    "GS-5001": 403,
    "GS-5002": 403,
    # Configuration errors (6000-6999) -> 500 Internal Server Error
    "GS-6000": 500,
    "GS-6001": 500,
    # Timeout errors (7000-7999) -> 504 Gateway Timeout
    "GS-7000": 504,
    "GS-7001": 504,
    "GS-7002": 504,
    # Authentication errors (8000-8999) -> 401 Unauthorized
    "GS-8000": 401,
    "GS-8001": 401,
    # Rate limit errors (9000-9999) -> 429 Too Many Requests
    "GS-9000": 429,
}


def get_http_status(error_code: str) -> int:
    """Get HTTP status code for error code."""
    return ERROR_CODE_TO_HTTP_STATUS.get(error_code, 500)