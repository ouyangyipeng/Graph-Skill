"""
Parser-Validator Integration Tests.

Test the collaboration workflow between parser and validator modules.
"""

from __future__ import annotations

import pytest
import yaml
from pathlib import Path
from datetime import datetime
from typing import Any

from graphskill.ingestion.parser.yaml_parser import YAMLParser, YAMLValidationError
from graphskill.ingestion.parser.markdown_parser import MarkdownParser, ParsedSkillFile
from graphskill.ingestion.validator.schema_validator import SchemaValidator
from graphskill.ingestion.validator.permission_validator import PermissionValidator
from graphskill.ingestion.validator.static_validator import StaticValidator


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def parser() -> YAMLParser:
    """Create default parser instance."""
    return YAMLParser(strict_mode=True)


@pytest.fixture
def lenient_parser() -> YAMLParser:
    """Create lenient parser instance."""
    return YAMLParser(strict_mode=False)


@pytest.fixture
def markdown_parser() -> MarkdownParser:
    """Create markdown parser instance."""
    return MarkdownParser()


@pytest.fixture
def schema_validator() -> SchemaValidator:
    """Create schema validator instance."""
    return SchemaValidator(strict_mode=False)


@pytest.fixture
def permission_validator() -> PermissionValidator:
    """Create permission validator instance."""
    return PermissionValidator(strict_mode=False)


@pytest.fixture
def static_validator() -> StaticValidator:
    """Create static validator instance."""
    return StaticValidator(strict_mode=False)


@pytest.fixture
def valid_frontmatter_dict() -> dict[str, Any]:
    """Valid frontmatter as dictionary."""
    return {
        "skill_id": "git:commit_changes",
        "version": "1.0.0",
        "intent_description": "Execute Git commit operation with proper message formatting and staging verification. This skill handles the complete commit workflow including pre-commit checks.",
        "permissions": [
            "fs:read:/tmp",
            "fs:write:/tmp",
            "net:http:github.com",
        ],
        "tags": ["git", "version-control", "commit"],
        "author": "test-author",
        "topology_hints": {
            "requires": ["git:init_repo"],
            "conflicts_with": ["git:reset_hard"],
            "enhances": ["git:push_changes"],
            "substitutes": ["git:commit_amend"],
        },
    }


@pytest.fixture
def invalid_frontmatter_missing_field() -> dict[str, Any]:
    """Invalid frontmatter missing required field."""
    return {
        "skill_id": "git:commit_changes",
        "version": "1.0.0",
        # Missing intent_description
        "permissions": ["fs:read:/tmp"],
    }


@pytest.fixture
def invalid_frontmatter_bad_permission() -> dict[str, Any]:
    """Invalid frontmatter with bad permission format."""
    return {
        "skill_id": "git:commit_changes",
        "version": "1.0.0",
        "intent_description": "Execute Git commit operation with proper message formatting and staging verification. This skill handles the complete commit workflow including pre-commit checks.",
        "permissions": ["invalid_permission_format"],
    }


@pytest.fixture
def valid_skill_markdown_content() -> str:
    """Valid skill markdown content."""
    return """---
skill_id: git:commit_changes
version: 1.0.0
intent_description: Execute Git commit operation with proper message formatting and staging verification. This skill handles the complete commit workflow including pre-commit checks.
permissions:
  - fs:read:/tmp
  - fs:write:/tmp
  - net:http:github.com
tags:
  - git
  - version-control
author: test-author
topology_hints:
  requires:
    - git:init_repo
  enhances:
    - git:push_changes
---

## Implementation

```python
def execute_commit():
    pass
```
"""


@pytest.fixture
def temp_skill_file(tmp_path: Path, valid_skill_markdown_content: str) -> Path:
    """Create temporary skill file."""
    skill_file = tmp_path / "test_skill.md"
    skill_file.write_text(valid_skill_markdown_content)
    return skill_file


# ============================================================================
# Parser Integration Tests
# ============================================================================


class TestYAMLParserIntegration:
    """YAMLParser integration tests."""
    
    @pytest.mark.asyncio
    async def test_yaml_parser_parse_valid_dict(
        self, parser: YAMLParser, valid_frontmatter_dict: dict[str, Any]
    ) -> None:
        """Test YAMLParser parsing valid dictionary."""
        result = parser.parse(valid_frontmatter_dict)
        
        assert result is not None
        assert result.skill_id == "git:commit_changes"
        assert result.version == "1.0.0"
        assert len(result.permissions) == 3
        assert "fs:read:/tmp" in result.permissions
        assert result.intent_description.startswith("Execute Git")
    
    @pytest.mark.asyncio
    async def test_yaml_parser_parse_invalid_dict(
        self, parser: YAMLParser, invalid_frontmatter_missing_field: dict[str, Any]
    ) -> None:
        """Test YAMLParser parsing invalid dictionary (missing required field)."""
        with pytest.raises(YAMLValidationError):
            parser.parse(invalid_frontmatter_missing_field)
    
    @pytest.mark.asyncio
    async def test_yaml_parser_lenient_mode(
        self, lenient_parser: YAMLParser, invalid_frontmatter_missing_field: dict[str, Any]
    ) -> None:
        """Test YAMLParser in lenient mode."""
        result = lenient_parser.parse(invalid_frontmatter_missing_field)
        # In lenient mode, should return result with warnings
        assert result is not None
        assert len(result.parse_warnings) > 0


class TestMarkdownParserIntegration:
    """MarkdownParser integration tests."""
    
    @pytest.mark.asyncio
    async def test_markdown_parser_parse_valid_file(
        self, markdown_parser: MarkdownParser, temp_skill_file: Path
    ) -> None:
        """Test MarkdownParser parsing valid file."""
        # MarkdownParser.parse() expects a Path, not a string
        result = markdown_parser.parse(temp_skill_file)
        
        assert result is not None
        assert result.skill_id == "git:commit_changes"
        assert result.version == "1.0.0"
        assert len(result.frontmatter.get("permissions", [])) == 3
    
    @pytest.mark.asyncio
    async def test_markdown_parser_extract_code_blocks(
        self, markdown_parser: MarkdownParser, temp_skill_file: Path
    ) -> None:
        """Test MarkdownParser extracting code blocks."""
        result = markdown_parser.parse(temp_skill_file)
        
        assert result is not None
        assert len(result.code_blocks) >= 1
        # Check first code block is Python
        if result.code_blocks:
            assert result.code_blocks[0].language == "python"


# ============================================================================
# Validator Integration Tests
# ============================================================================


class TestSchemaValidatorIntegration:
    """SchemaValidator integration tests."""
    
    @pytest.mark.asyncio
    async def test_schema_validator_validate_valid_manifest(
        self, parser: YAMLParser, schema_validator: SchemaValidator, valid_frontmatter_dict: dict[str, Any]
    ) -> None:
        """Test SchemaValidator validating valid Manifest."""
        manifest = parser.parse(valid_frontmatter_dict)
        # SchemaValidator.validate() expects a dict (raw_data), not ParsedFrontmatter
        result = schema_validator.validate(manifest.raw_data)
        
        assert result.is_valid == True
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_schema_validator_validate_invalid_manifest(
        self, lenient_parser: YAMLParser, schema_validator: SchemaValidator, invalid_frontmatter_missing_field: dict[str, Any]
    ) -> None:
        """Test SchemaValidator validating invalid Manifest."""
        manifest = lenient_parser.parse(invalid_frontmatter_missing_field)
        result = schema_validator.validate(manifest.raw_data)
        
        assert result.is_valid == False
        assert len(result.errors) > 0
    
    @pytest.mark.asyncio
    async def test_schema_validator_validate_permission_format(
        self, lenient_parser: YAMLParser, schema_validator: SchemaValidator, invalid_frontmatter_bad_permission: dict[str, Any]
    ) -> None:
        """Test SchemaValidator validating permission format."""
        manifest = lenient_parser.parse(invalid_frontmatter_bad_permission)
        result = schema_validator.validate(manifest.raw_data)
        
        assert result.is_valid == False
        # Check for permission-related errors
        permission_errors = [e for e in result.errors if "permission" in e.path.lower()]
        assert len(permission_errors) > 0


class TestPermissionValidatorIntegration:
    """PermissionValidator integration tests."""
    
    @pytest.mark.asyncio
    async def test_permission_validator_validate_valid_permissions(
        self, parser: YAMLParser, permission_validator: PermissionValidator, valid_frontmatter_dict: dict[str, Any]
    ) -> None:
        """Test PermissionValidator validating valid permissions."""
        manifest = parser.parse(valid_frontmatter_dict)
        # PermissionValidator.validate() expects list[str]
        result = permission_validator.validate(manifest.permissions)
        
        assert result.is_valid == True
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_permission_validator_validate_invalid_permissions(
        self, lenient_parser: YAMLParser, permission_validator: PermissionValidator, invalid_frontmatter_bad_permission: dict[str, Any]
    ) -> None:
        """Test PermissionValidator validating invalid permissions."""
        manifest = lenient_parser.parse(invalid_frontmatter_bad_permission)
        result = permission_validator.validate(manifest.permissions)
        
        assert result.is_valid == False
        assert len(result.errors) > 0
    
    @pytest.mark.asyncio
    async def test_permission_validator_check_scope_levels(self, permission_validator: PermissionValidator) -> None:
        """Test PermissionValidator checking scope and level."""
        # Test valid scope and level
        valid_perms = ["fs:read:/tmp", "net:http:github.com"]
        result = permission_validator.validate(valid_perms)
        assert result.is_valid == True
        
        # Test invalid scope
        invalid_scope_perms = ["invalid_scope:read:/tmp"]
        result = permission_validator.validate(invalid_scope_perms)
        assert result.is_valid == False
        
        # Test invalid level
        invalid_level_perms = ["fs:invalid_level:/tmp"]
        result = permission_validator.validate(invalid_level_perms)
        assert result.is_valid == False


class TestStaticValidatorIntegration:
    """StaticValidator integration tests."""
    
    @pytest.mark.asyncio
    async def test_static_validator_validate_valid_code_blocks(
        self, markdown_parser: MarkdownParser, static_validator: StaticValidator, temp_skill_file: Path
    ) -> None:
        """Test StaticValidator validating valid code blocks."""
        parsed_file = markdown_parser.parse(temp_skill_file)
        
        # StaticValidator.validate_code_blocks() expects list[dict]
        code_blocks_dict = [
            {
                "language": block.language,
                "code": block.code,
                "line_start": block.line_start,
            }
            for block in parsed_file.code_blocks
        ]
        
        result = static_validator.validate_code_blocks(code_blocks_dict, temp_skill_file)
        
        # Should not have syntax errors for valid Python code
        assert result.has_errors == False
    
    @pytest.mark.asyncio
    async def test_static_validator_detect_warnings(
        self, static_validator: StaticValidator, tmp_path: Path
    ) -> None:
        """Test StaticValidator detecting code issues (warnings/info)."""
        # Create a file with valid Python syntax but missing entrypoint
        code_blocks = [
            {
                "language": "python",
                "code": "def helper_function():\n    pass",
                "line_start": 1,
            }
        ]
        
        result = static_validator.validate_code_blocks(code_blocks)
        
        # Should detect warnings (missing entrypoint, missing docstring)
        # Note: Syntax error detection requires Tree-sitter which may not be installed
        assert result.has_warnings == True or result.info_count > 0
        assert result.total_issues > 0


# ============================================================================
# Full Pipeline Integration Tests
# ============================================================================


class TestParserValidatorPipeline:
    """Parser-Validator complete pipeline integration tests."""
    
    @pytest.mark.asyncio
    async def test_full_pipeline_valid_skill(
        self, markdown_parser: MarkdownParser, schema_validator: SchemaValidator,
        permission_validator: PermissionValidator, static_validator: StaticValidator,
        temp_skill_file: Path
    ) -> None:
        """Test complete pipeline processing valid skill file."""
        # Parse file
        parsed_file = markdown_parser.parse(temp_skill_file)
        
        # Validate schema
        schema_result = schema_validator.validate(parsed_file.frontmatter)
        assert schema_result.is_valid == True
        
        # Validate permissions
        permissions = parsed_file.frontmatter.get("permissions", [])
        permission_result = permission_validator.validate(permissions)
        assert permission_result.is_valid == True
        
        # Validate code blocks
        code_blocks_dict = [
            {
                "language": block.language,
                "code": block.code,
                "line_start": block.line_start,
            }
            for block in parsed_file.code_blocks
        ]
        static_result = static_validator.validate_code_blocks(code_blocks_dict)
        assert static_result.has_errors == False
    
    @pytest.mark.asyncio
    async def test_full_pipeline_invalid_skill(
        self, lenient_parser: YAMLParser, schema_validator: SchemaValidator,
        invalid_frontmatter_bad_permission: dict[str, Any]
    ) -> None:
        """Test complete pipeline processing invalid skill."""
        # Parse
        manifest = lenient_parser.parse(invalid_frontmatter_bad_permission)
        
        # Validate - should fail
        schema_result = schema_validator.validate(manifest.raw_data)
        assert schema_result.is_valid == False
    
    @pytest.mark.asyncio
    async def test_parser_validator_batch_processing(
        self, markdown_parser: MarkdownParser, schema_validator: SchemaValidator, tmp_path: Path
    ) -> None:
        """Test batch processing of multiple skill files."""
        # Create multiple skill files
        skill_files = []
        for i in range(3):
            skill_file = tmp_path / f"skill_{i}.md"
            content = f"""---
skill_id: test:skill_{i}
version: 1.0.0
intent_description: Test skill {i} for batch processing integration testing with sufficient length description.
permissions:
  - fs:read:/tmp
---
"""
            skill_file.write_text(content)
            skill_files.append(skill_file)
        
        # Batch process
        results = []
        for skill_file in skill_files:
            parsed_file = markdown_parser.parse(skill_file)
            validation_result = schema_validator.validate(parsed_file.frontmatter)
            results.append((parsed_file, validation_result))
        
        # Verify all results
        assert len(results) == 3
        for parsed_file, validation_result in results:
            assert validation_result.is_valid == True
            assert parsed_file.skill_id.startswith("test:skill_")
        
        # Cleanup
        for skill_file in skill_files:
            skill_file.unlink()


class TestYAMLStringParsing:
    """Test YAML string parsing integration."""
    
    @pytest.mark.asyncio
    async def test_yaml_parser_parse_yaml_string(
        self, parser: YAMLParser, valid_skill_markdown_content: str
    ) -> None:
        """Test YAMLParser.parse_yaml_string() method."""
        # Extract YAML frontmatter from markdown content
        yaml_content = """skill_id: git:commit_changes
version: 1.0.0
intent_description: Execute Git commit operation with proper message formatting and staging verification. This skill handles the complete commit workflow including pre-commit checks.
permissions:
  - fs:read:/tmp
  - fs:write:/tmp
  - net:http:github.com
"""
        
        result = parser.parse_yaml_string(yaml_content)
        
        assert result is not None
        assert result.skill_id == "git:commit_changes"
        assert result.version == "1.0.0"
        assert len(result.permissions) == 3
    
    @pytest.mark.asyncio
    async def test_yaml_parser_parse_invalid_yaml_string(
        self, parser: YAMLParser
    ) -> None:
        """Test YAMLParser parsing invalid YAML string."""
        invalid_yaml = "skill_id: test\nversion: [broken\n"
        
        with pytest.raises(YAMLValidationError):
            parser.parse_yaml_string(invalid_yaml)


class TestCrossModuleIntegration:
    """Test cross-module integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_yaml_to_schema_validation_pipeline(
        self, parser: YAMLParser, schema_validator: SchemaValidator
    ) -> None:
        """Test YAML parsing to schema validation pipeline."""
        yaml_string = """skill_id: db:query_postgres
version: 2.1.0
intent_description: Execute PostgreSQL database queries with proper connection handling and result formatting. This skill supports both simple and complex query operations.
permissions:
  - db:query:postgres
  - db:read:postgres
tags:
  - database
  - postgres
  - sql
"""
        
        # Parse YAML
        parsed = parser.parse_yaml_string(yaml_string)
        
        # Validate schema
        schema_result = schema_validator.validate(parsed.raw_data)
        
        assert parsed.skill_id == "db:query_postgres"
        assert schema_result.is_valid == True
    
    @pytest.mark.asyncio
    async def test_permission_high_risk_detection(
        self, permission_validator: PermissionValidator
    ) -> None:
        """Test permission validator detecting high-risk permissions."""
        # Include some high-risk permissions (using valid format)
        permissions = [
            "fs:read:/tmp",       # Normal
            "fs:delete:/",        # High-risk (delete any file)
            "net:connect:*",      # High-risk (connect to any address) - but invalid format
        ]
        
        result = permission_validator.validate(permissions)
        
        # fs:delete:/ is valid format and high-risk
        # net:connect:* is invalid format (target must match hostname pattern)
        # So we expect at least one high-risk permission detected
        assert result.high_risk_count >= 1
        # Check that fs:delete:/ is flagged as high-risk
        high_risk_perms = [p.raw_permission for p in result.high_risk_permissions]
        assert "fs:delete:/" in high_risk_perms