---
skill_id: "db:query"
version: "1.0.0"
intent_description: "Execute database queries with support for multiple database types including PostgreSQL MySQL Redis Neo4j with consistent result formatting and error handling"
permissions:
  - "db:read:postgres"
  - "db:read:mysql"
  - "db:read:redis"
  - "db:read:neo4j"
topology_hints:
  requires:
    - "db:connect"
  provides:
    - "db:results"
    - "db:metadata"
  conflicts:
    - "db:write"
    - "db:delete"
tags:
  - "database"
  - "query"
  - "sql"
  - "nosql"
author: "GraphSkill Team"
---

# Database Query Skill

## Description

This skill executes database queries across multiple database types. It supports SQL databases (PostgreSQL, MySQL) and NoSQL databases (Redis, Neo4j). Results are formatted consistently regardless of the underlying database.

## Usage

```python
# SQL query
results = execute_query("postgres", "SELECT * FROM users WHERE active = true")

# Redis query
value = execute_query("redis", "GET user:123")

# Neo4j query
nodes = execute_query("neo4j", "MATCH (n:User) RETURN n LIMIT 10")
```

## Code Implementation

```python
from typing import Optional, Union, Any, list[dict]
from dataclasses import dataclass
from enum import Enum

class DatabaseType(str, Enum):
    POSTGRES = "postgres"
    MYSQL = "mysql"
    REDIS = "redis"
    NEO4J = "neo4j"
    MONGODB = "mongodb"

@dataclass
class QueryResult:
    database: str
    query: str
    rows: list[dict]
    row_count: int
    execution_time_ms: float
    metadata: dict[str, Any]

def execute_query(
    database_type: Union[str, DatabaseType],
    query: str,
    connection_params: Optional[dict] = None,
    timeout: int = 30
) -> QueryResult:
    """
    Execute a database query.
    
    Args:
        database_type: Type of database.
        query: Query string.
        connection_params: Connection parameters.
        timeout: Query timeout in seconds.
    
    Returns:
        Query result with rows and metadata.
    """
    import time
    
    db_type = DatabaseType(database_type) if isinstance(database_type, str) else database_type
    start_time = time.time()
    
    # Placeholder implementation - would use actual database drivers
    if db_type == DatabaseType.POSTGRES:
        results = _execute_sql_query(query, connection_params, timeout)
    elif db_type == DatabaseType.MYSQL:
        results = _execute_sql_query(query, connection_params, timeout)
    elif db_type == DatabaseType.REDIS:
        results = _execute_redis_query(query, connection_params, timeout)
    elif db_type == DatabaseType.NEO4J:
        results = _execute_cypher_query(query, connection_params, timeout)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
    
    execution_time = (time.time() - start_time) * 1000
    
    return QueryResult(
        database=db_type.value,
        query=query,
        rows=results,
        row_count=len(results),
        execution_time_ms=execution_time,
        metadata={"timeout": timeout}
    )

def _execute_sql_query(
    query: str,
    params: Optional[dict],
    timeout: int
) -> list[dict]:
    """
    Execute SQL query (PostgreSQL/MySQL).
    
    Args:
        query: SQL query string.
        params: Connection parameters.
        timeout: Query timeout.
    
    Returns:
        List of result rows as dicts.
    """
    # Placeholder - would use psycopg2 or mysql connector
    # Simulated response for testing
    if "SELECT" in query.upper():
        return [{"id": 1, "name": "test", "active": True}]
    return []

def _execute_redis_query(
    query: str,
    params: Optional[dict],
    timeout: int
) -> list[dict]:
    """
    Execute Redis command.
    
    Args:
        query: Redis command.
        params: Connection parameters.
        timeout: Command timeout.
    
    Returns:
        Redis response as dict.
    """
    # Placeholder - would use redis-py
    parts = query.split()
    command = parts[0].upper()
    
    if command == "GET":
        return [{"key": parts[1] if len(parts) > 1 else "", "value": None}]
    elif command == "KEYS":
        return [{"keys": []}]
    return [{"result": "OK"}]

def _execute_cypher_query(
    query: str,
    params: Optional[dict],
    timeout: int
) -> list[dict]:
    """
    Execute Neo4j Cypher query.
    
    Args:
        query: Cypher query string.
        params: Connection parameters.
        timeout: Query timeout.
    
    Returns:
        List of nodes/relationships as dicts.
    """
    # Placeholder - would use neo4j driver
    if "MATCH" in query.upper():
        return [{"node": {"id": 1, "labels": ["User"], "properties": {}}}]
    return []

def connect_database(
    database_type: Union[str, DatabaseType],
    connection_string: str
) -> bool:
    """
    Establish database connection.
    
    Args:
        database_type: Type of database.
        connection_string: Connection string.
    
    Returns:
        True if connected successfully.
    """
    # Placeholder - would establish actual connection
    return True
```

## Entry Point

- `execute_query(database_type: Union[str, DatabaseType], query: str, ...) -> QueryResult`

## Dependencies

- Requires `db:connect` skill to establish connection
- Provides `db:results` and `db:metadata` for data processing
- Conflicts with `db:write` and `db:delete` for safety

## Error Handling

- Raises `ValueError` for unsupported database types
- Handles connection timeouts
- Returns empty results for failed queries