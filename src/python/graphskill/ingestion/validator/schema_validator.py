"""
Schema 校验器。

验证 SKILL.md 文件的 YAML Frontmatter 是否符合 JSON Schema 规范。

Reference: RFC-01 Section 2.2, RFC-02 Section 3.3
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

from graphskill.core.exceptions import IngestionError


@dataclass
class ValidationError:
    """单个验证错误。"""
    
    path: str
    message: str
    value: Optional[Any] = None
    validator: Optional[str] = None
    schema_path: Optional[str] = None
    
    def to_dict(self) -> dict:
        result = {
            "path": self.path,
            "message": self.message,
        }
        if self.value is not None:
            result["value"] = str(self.value)
        if self.validator:
            result["validator"] = self.validator
        if self.schema_path:
            result["schema_path"] = self.schema_path
        return result


@dataclass
class ValidationResult:
    """验证结果。"""
    
    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    validated_data: Optional[dict] = None
    
    @property
    def error_count(self) -> int:
        """错误数量。"""
        return len(self.errors)
    
    @property
    def warning_count(self) -> int:
        """警告数量。"""
        return len(self.warnings)
    
    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": self.warnings,
        }


class SchemaValidationError(IngestionError):
    """Schema 验证错误。
    
    Error Code: GS-2010
    """
    
    def __init__(
        self,
        message: str,
        errors: Optional[list[ValidationError]] = None,
        file_path: Optional[Path] = None,
    ):
        super().__init__(message)
        self.code = "GS-2010"
        self.errors = errors or []
        self.file_path = file_path
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        result["errors"] = [e.to_dict() for e in self.errors]
        if self.file_path:
            result["file_path"] = str(self.file_path)
        return result


# JSON Schema 定义 (skill-manifest-v1)
SKILL_MANIFEST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "skill-manifest-v1",
    "title": "Skill Manifest Schema",
    "description": "Schema for SKILL.md YAML Frontmatter",
    "type": "object",
    "required": ["skill_id", "version", "intent_description", "permissions"],
    "properties": {
        "skill_id": {
            "type": "string",
            "pattern": "^[a-z0-9_-]+:[a-z0-9_-]+$",
            "description": "Unique skill identifier in namespace:name format",
            "examples": ["git:commit_changes", "db:query_postgres"],
        },
        "version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+(-[a-zA-Z0-9]+)?$",
            "description": "Version number following SemVer specification",
            "examples": ["1.0.0", "2.1.3-beta"],
        },
        "intent_description": {
            "type": "string",
            "minLength": 50,
            "maxLength": 500,
            "description": "Clear description of skill intent (50-500 characters)",
        },
        "permissions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "string",
                "pattern": "^[a-z]+:[a-z]+(:[a-zA-Z0-9_/.-]+)?$",
            },
            "description": "List of required permissions",
            "examples": [["fs:read:/tmp", "net:http:github.com"]],
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional skill tags for categorization",
        },
        "author": {
            "type": "string",
            "description": "Author information",
        },
        "created_at": {
            "type": "string",
            "pattern": "^\\d{4}-\\d{2}-\\d{2}(T\\d{2}:\\d{2}:\\d{2})?",
            "description": "Creation timestamp",
        },
        "updated_at": {
            "type": "string",
            "pattern": "^\\d{4}-\\d{2}-\\d{2}(T\\d{2}:\\d{2}:\\d{2})?",
            "description": "Last update timestamp",
        },
        "min_agent_version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+$",
            "description": "Minimum compatible agent version",
        },
        "max_agent_version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+$",
            "description": "Maximum compatible agent version",
        },
        "deprecated": {
            "type": "boolean",
            "default": False,
            "description": "Whether the skill is deprecated",
        },
        "deprecation_message": {
            "type": "string",
            "description": "Deprecation notice message",
        },
        "success_rate": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Historical success rate (0-1)",
        },
        "avg_latency_ms": {
            "type": "integer",
            "minimum": 0,
            "description": "Average execution latency in milliseconds",
        },
        "topology_hints": {
            "type": "object",
            "properties": {
                "requires": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Skills that this skill requires",
                },
                "conflicts_with": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Skills that conflict with this skill",
                },
                "enhances": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Skills that this skill enhances",
                },
                "substitutes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Skills that this skill can substitute",
                },
            },
            "additionalProperties": False,
            "description": "Topology relationship hints",
        },
    },
    "additionalProperties": True,  # Allow extra fields with warning
}


class SchemaValidator:
    """
    Schema 校验器。
    
    验证 Frontmatter 是否符合 JSON Schema 规范。
    
    Features:
        - JSON Schema 验证
        - 必填字段检查
        - 格式规范验证
        - 详细错误报告
    
    Example:
        >>> validator = SchemaValidator()
        >>> result = validator.validate(frontmatter_dict)
        >>> if not result.is_valid:
        ...     for error in result.errors:
        ...         print(f"{error.path}: {error.message}")
    """
    
    def __init__(self, strict_mode: bool = True, schema: Optional[dict] = None):
        """
        初始化校验器。
        
        Args:
            strict_mode: 严格模式，启用时对验证失败抛出异常
            schema: 自定义 JSON Schema（默认使用内置 Schema）
        """
        self.strict_mode = strict_mode
        self.schema = schema or SKILL_MANIFEST_SCHEMA
        self._jsonschema_available = self._check_jsonschema()
    
    def _check_jsonschema(self) -> bool:
        """检查 jsonschema 库是否可用。"""
        try:
            import jsonschema  # noqa: F401
            return True
        except ImportError:
            return False
    
    def validate(
        self,
        data: dict,
        file_path: Optional[Path] = None,
    ) -> ValidationResult:
        """
        验证数据。
        
        Args:
            data: 待验证的 Frontmatter 字典
            file_path: 源文件路径（用于错误报告）
            
        Returns:
            ValidationResult: 验证结果
            
        Raises:
            SchemaValidationError: 验证失败（严格模式）
        """
        errors: list[ValidationError] = []
        warnings: list[str] = []
        
        if self._jsonschema_available:
            # 使用 jsonschema 库验证
            errors, warnings = self._validate_with_jsonschema(data)
        else:
            # 使用内置验证逻辑
            errors, warnings = self._validate_builtin(data)
        
        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            validated_data=data if len(errors) == 0 else None,
        )
        
        if self.strict_mode and not result.is_valid:
            raise SchemaValidationError(
                f"Schema validation failed with {len(errors)} errors",
                errors=errors,
                file_path=file_path,
            )
        
        return result
    
    def _validate_with_jsonschema(
        self,
        data: dict,
    ) -> tuple[list[ValidationError], list[str]]:
        """
        使用 jsonschema 库验证。
        
        Args:
            data: 待验证数据
            
        Returns:
            tuple: (errors, warnings)
        """
        import jsonschema
        from jsonschema import validators, exceptions
        
        errors: list[ValidationError] = []
        warnings: list[str] = []
        
        try:
            # 使用 Draft7Validator
            validator_cls = validators.Draft7Validator
            validator = validator_cls(self.schema)
            
            # 收集所有验证错误
            for error in validator.iter_errors(data):
                path = ".".join(str(p) for p in error.absolute_path) or "root"
                errors.append(ValidationError(
                    path=path,
                    message=error.message,
                    value=error.instance if hasattr(error, "instance") else None,
                    validator=error.validator,
                    schema_path=".".join(str(p) for p in error.absolute_schema_path),
                ))
            
            # 检查额外字段
            schema_props = self.schema.get("properties", {}).keys()
            extra_fields = set(data.keys()) - set(schema_props) - set(self.schema.get("required", []))
            for field in extra_fields:
                if field not in schema_props:
                    warnings.append(f"Extra field not in schema: {field}")
        
        except jsonschema.SchemaError as e:
            errors.append(ValidationError(
                path="schema",
                message=f"Schema error: {e}",
            ))
        
        return errors, warnings
    
    def _validate_builtin(
        self,
        data: dict,
    ) -> tuple[list[ValidationError], list[str]]:
        """
        内置验证逻辑（无 jsonschema 库时使用）。
        
        Args:
            data: 待验证数据
            
        Returns:
            tuple: (errors, warnings)
        """
        import re
        
        errors: list[ValidationError] = []
        warnings: list[str] = []
        
        schema_props = self.schema.get("properties", {})
        required_fields = self.schema.get("required", [])
        
        # 检查必填字段
        for field in required_fields:
            if field not in data:
                errors.append(ValidationError(
                    path=field,
                    message=f"Required field '{field}' is missing",
                    validator="required",
                ))
        
        # 检查字段类型和格式
        for field, value in data.items():
            if field not in schema_props:
                warnings.append(f"Extra field not in schema: {field}")
                continue
            
            field_schema = schema_props[field]
            expected_type = field_schema.get("type")
            
            # 类型检查
            if expected_type:
                type_valid = self._check_type(value, expected_type)
                if not type_valid:
                    errors.append(ValidationError(
                        path=field,
                        message=f"Field '{field}' has wrong type: expected {expected_type}",
                        value=value,
                        validator="type",
                    ))
                    continue
            
            # 字符串格式检查
            if isinstance(value, str):
                # pattern 检查
                pattern = field_schema.get("pattern")
                if pattern and not re.match(pattern, value):
                    errors.append(ValidationError(
                        path=field,
                        message=f"Field '{field}' does not match pattern: {pattern}",
                        value=value,
                        validator="pattern",
                    ))
                
                # minLength 检查
                min_length = field_schema.get("minLength")
                if min_length and len(value) < min_length:
                    errors.append(ValidationError(
                        path=field,
                        message=f"Field '{field}' is too short: minimum {min_length} characters",
                        value=value,
                        validator="minLength",
                    ))
                
                # maxLength 检查
                max_length = field_schema.get("maxLength")
                if max_length and len(value) > max_length:
                    errors.append(ValidationError(
                        path=field,
                        message=f"Field '{field}' is too long: maximum {max_length} characters",
                        value=value,
                        validator="maxLength",
                    ))
            
            # 数值范围检查
            if isinstance(value, (int, float)):
                minimum = field_schema.get("minimum")
                if minimum is not None and value < minimum:
                    errors.append(ValidationError(
                        path=field,
                        message=f"Field '{field}' is below minimum: {minimum}",
                        value=value,
                        validator="minimum",
                    ))
                
                maximum = field_schema.get("maximum")
                if maximum is not None and value > maximum:
                    errors.append(ValidationError(
                        path=field,
                        message=f"Field '{field}' is above maximum: {maximum}",
                        value=value,
                        validator="maximum",
                    ))
            
            # 数组检查
            if isinstance(value, list):
                min_items = field_schema.get("minItems")
                if min_items and len(value) < min_items:
                    errors.append(ValidationError(
                        path=field,
                        message=f"Field '{field}' has too few items: minimum {min_items}",
                        value=value,
                        validator="minItems",
                    ))
                
                # 数组项检查
                items_schema = field_schema.get("items")
                if items_schema and isinstance(items_schema, dict):
                    item_type = items_schema.get("type")
                    item_pattern = items_schema.get("pattern")
                    
                    for i, item in enumerate(value):
                        if item_type and not self._check_type(item, item_type):
                            errors.append(ValidationError(
                                path=f"{field}[{i}]",
                                message=f"Array item has wrong type: expected {item_type}",
                                value=item,
                                validator="items.type",
                            ))
                        
                        if item_pattern and isinstance(item, str) and not re.match(item_pattern, item):
                            errors.append(ValidationError(
                                path=f"{field}[{i}]",
                                message=f"Array item does not match pattern: {item_pattern}",
                                value=item,
                                validator="items.pattern",
                            ))
        
        return errors, warnings
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """
        检查值类型。
        
        Args:
            value: 待检查值
            expected_type: JSON Schema 类型名称
            
        Returns:
            bool: 类型是否匹配
        """
        type_mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type is None:
            return True  # 未知类型，跳过检查
        
        return isinstance(value, expected_python_type)
    
    def validate_file(
        self,
        file_path: Path,
    ) -> ValidationResult:
        """
        验证文件。
        
        Args:
            file_path: 技能文件路径
            
        Returns:
            ValidationResult: 验证结果
        """
        import yaml
        
        if not file_path.exists():
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    path="file",
                    message=f"File not found: {file_path}",
                )],
            )
        
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # 提取 Frontmatter
            import re
            pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
            match = pattern.match(content)
            
            if not match:
                return ValidationResult(
                    is_valid=False,
                    errors=[ValidationError(
                        path="frontmatter",
                        message="No valid YAML frontmatter found",
                    )],
                )
            
            yaml_content = match.group(1)
            frontmatter = yaml.safe_load(yaml_content)
            
            if not isinstance(frontmatter, dict):
                return ValidationResult(
                    is_valid=False,
                    errors=[ValidationError(
                        path="frontmatter",
                        message="Frontmatter must be a YAML dictionary",
                    )],
                )
            
            return self.validate(frontmatter, file_path)
        
        except yaml.YAMLError as e:
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    path="frontmatter",
                    message=f"YAML parsing error: {e}",
                )],
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    path="file",
                    message=f"File reading error: {e}",
                )],
            )
    
    def get_schema(self) -> dict:
        """
        获取当前使用的 Schema。
        
        Returns:
            dict: JSON Schema 定义
        """
        return self.schema
    
    def load_schema_from_file(self, schema_path: Path) -> None:
        """
        从文件加载 Schema。
        
        Args:
            schema_path: Schema 文件路径
        """
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                self.schema = json.load(f)
        except Exception as e:
            raise SchemaValidationError(
                f"Failed to load schema from {schema_path}: {e}"
            )