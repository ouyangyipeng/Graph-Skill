"""
YAML Frontmatter 解析器。

解析 SKILL.md 文件中的 YAML Frontmatter 元数据，
验证必填字段和格式规范。

Reference: RFC-01 Section 2.1, RFC-02 Section 3.2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

import yaml

from graphskill.core.exceptions import IngestionError


@dataclass
class ParsedFrontmatter:
    """解析后的 Frontmatter 结构。"""
    
    # 必填字段
    skill_id: str
    version: str
    intent_description: str
    permissions: list[str]
    
    # 可选字段
    tags: list[str] = field(default_factory=list)
    author: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    min_agent_version: Optional[str] = None
    max_agent_version: Optional[str] = None
    deprecated: bool = False
    deprecation_message: Optional[str] = None
    success_rate: Optional[float] = None
    avg_latency_ms: Optional[int] = None
    
    # 拓扑提示
    topology_hints: dict = field(default_factory=dict)
    
    # 原始数据
    raw_data: dict = field(default_factory=dict)
    
    # 元信息
    source_file: Optional[Path] = None
    parse_warnings: list[str] = field(default_factory=list)


class YAMLValidationError(IngestionError):
    """YAML 验证错误。
    
    Error Code: GS-2001 系列
    """
    
    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        field_value: Optional[Any] = None,
        file_path: Optional[Path] = None,
        line_number: Optional[int] = None,
    ):
        super().__init__(message)
        self.code = "GS-2001"
        self.field_name = field_name
        self.field_value = field_value
        self.file_path = file_path
        self.line_number = line_number
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        if self.field_name:
            result["field_name"] = self.field_name
        if self.field_value is not None:
            result["field_value"] = str(self.field_value)
        if self.file_path:
            result["file_path"] = str(self.file_path)
        if self.line_number:
            result["line_number"] = self.line_number
        return result


# 必填字段定义
REQUIRED_FIELDS = {
    "skill_id": {
        "type": str,
        "pattern": r"^[a-z0-9_-]+:[a-z0-9_-]+$",
        "description": "技能唯一标识，格式: namespace:name",
    },
    "version": {
        "type": str,
        "pattern": r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$",
        "description": "版本号，遵循 SemVer 规范",
    },
    "intent_description": {
        "type": str,
        "min_length": 50,
        "max_length": 500,
        "description": "意图描述，50-500 字符",
    },
    "permissions": {
        "type": list,
        "min_items": 1,
        "item_pattern": r"^[a-z]+:[a-z]+(:[a-zA-Z0-9_/.-]+)?$",
        "description": "权限声明列表，至少一项",
    },
}

# 可选字段定义
OPTIONAL_FIELDS = {
    "tags": {
        "type": list,
        "item_type": str,
        "description": "技能标签列表",
    },
    "author": {
        "type": str,
        "description": "作者信息",
    },
    "created_at": {
        "type": str,
        "pattern": r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?",
        "description": "创建时间",
    },
    "updated_at": {
        "type": str,
        "pattern": r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?",
        "description": "更新时间",
    },
    "min_agent_version": {
        "type": str,
        "pattern": r"^\d+\.\d+\.\d+$",
        "description": "最低 Agent 版本",
    },
    "max_agent_version": {
        "type": str,
        "pattern": r"^\d+\.\d+\.\d+$",
        "description": "最高 Agent 版本",
    },
    "deprecated": {
        "type": bool,
        "description": "是否已废弃",
    },
    "deprecation_message": {
        "type": str,
        "description": "废弃说明",
    },
    "success_rate": {
        "type": (int, float),
        "min": 0.0,
        "max": 1.0,
        "description": "成功率 (0-1)",
    },
    "avg_latency_ms": {
        "type": int,
        "min": 0,
        "description": "平均延迟 (毫秒)",
    },
    "topology_hints": {
        "type": dict,
        "description": "拓扑关系提示",
    },
}


class YAMLParser:
    """
    YAML Frontmatter 解析器。
    
    解析并验证 SKILL.md 文件中的 YAML Frontmatter。
    
    Features:
        - 必填字段验证
        - 格式规范检查
        - 类型安全转换
        - 拓扑提示解析
    
    Example:
        >>> parser = YAMLParser()
        >>> result = parser.parse(frontmatter_dict)
        >>> print(result.skill_id)
        git:commit_changes
    """
    
    def __init__(self, strict_mode: bool = True):
        """
        初始化解析器。
        
        Args:
            strict_mode: 严格模式，启用时对验证错误抛出异常
        """
        self.strict_mode = strict_mode
    
    def parse(
        self,
        frontmatter: dict,
        source_file: Optional[Path] = None,
    ) -> ParsedFrontmatter:
        """
        解析 Frontmatter。
        
        Args:
            frontmatter: YAML 解析后的字典
            source_file: 源文件路径（用于错误报告）
            
        Returns:
            ParsedFrontmatter: 解析结果
            
        Raises:
            YAMLValidationError: 验证错误
        """
        warnings: list[str] = []
        
        # 验证必填字段
        self._validate_required_fields(frontmatter, source_file, warnings)
        
        # 验证可选字段
        self._validate_optional_fields(frontmatter, source_file, warnings)
        
        # 提取拓扑提示
        topology_hints = self._extract_topology_hints(frontmatter, warnings)
        
        # 构建结果
        return ParsedFrontmatter(
            skill_id=frontmatter.get("skill_id", ""),
            version=frontmatter.get("version", ""),
            intent_description=frontmatter.get("intent_description", ""),
            permissions=frontmatter.get("permissions", []),
            tags=frontmatter.get("tags", []),
            author=frontmatter.get("author"),
            created_at=frontmatter.get("created_at"),
            updated_at=frontmatter.get("updated_at"),
            min_agent_version=frontmatter.get("min_agent_version"),
            max_agent_version=frontmatter.get("max_agent_version"),
            deprecated=frontmatter.get("deprecated", False),
            deprecation_message=frontmatter.get("deprecation_message"),
            success_rate=frontmatter.get("success_rate"),
            avg_latency_ms=frontmatter.get("avg_latency_ms"),
            topology_hints=topology_hints,
            raw_data=frontmatter,
            source_file=source_file,
            parse_warnings=warnings,
        )
    
    def parse_yaml_string(
        self,
        yaml_content: str,
        source_file: Optional[Path] = None,
    ) -> ParsedFrontmatter:
        """
        解析 YAML 字符串。
        
        Args:
            yaml_content: YAML 内容字符串
            source_file: 源文件路径
            
        Returns:
            ParsedFrontmatter: 解析结果
            
        Raises:
            YAMLValidationError: YAML 解析或验证错误
        """
        try:
            frontmatter = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise YAMLValidationError(
                f"YAML parsing error: {e}",
                file_path=source_file,
            )
        
        if not isinstance(frontmatter, dict):
            raise YAMLValidationError(
                "Frontmatter must be a YAML dictionary/mapping",
                file_path=source_file,
            )
        
        return self.parse(frontmatter, source_file)
    
    def _validate_required_fields(
        self,
        frontmatter: dict,
        source_file: Optional[Path],
        warnings: list[str],
    ) -> None:
        """
        验证必填字段。
        
        Args:
            frontmatter: Frontmatter 字典
            source_file: 源文件路径
            warnings: 警告列表
            
        Raises:
            YAMLValidationError: 验证错误
        """
        import re
        
        for field_name, field_spec in REQUIRED_FIELDS.items():
            value = frontmatter.get(field_name)
            
            # 检查字段存在
            if value is None:
                if self.strict_mode:
                    raise YAMLValidationError(
                        f"Required field '{field_name}' is missing",
                        field_name=field_name,
                        file_path=source_file,
                    )
                warnings.append(f"Missing required field: {field_name}")
                continue
            
            # 检查类型
            expected_type = field_spec["type"]
            if not isinstance(value, expected_type):
                if self.strict_mode:
                    raise YAMLValidationError(
                        f"Field '{field_name}' has wrong type: expected {expected_type.__name__}, got {type(value).__name__}",
                        field_name=field_name,
                        field_value=value,
                        file_path=source_file,
                    )
                warnings.append(f"Wrong type for {field_name}: expected {expected_type.__name__}")
                continue
            
            # 检查模式匹配
            if "pattern" in field_spec:
                pattern = field_spec["pattern"]
                if not re.match(pattern, str(value)):
                    if self.strict_mode:
                        raise YAMLValidationError(
                            f"Field '{field_name}' does not match pattern: {pattern}",
                            field_name=field_name,
                            field_value=value,
                            file_path=source_file,
                        )
                    warnings.append(f"Invalid format for {field_name}")
            
            # 检查字符串长度
            if isinstance(value, str):
                if "min_length" in field_spec and len(value) < field_spec["min_length"]:
                    if self.strict_mode:
                        raise YAMLValidationError(
                            f"Field '{field_name}' is too short: minimum {field_spec['min_length']} characters",
                            field_name=field_name,
                            field_value=value,
                            file_path=source_file,
                        )
                    warnings.append(f"{field_name} too short")
                
                if "max_length" in field_spec and len(value) > field_spec["max_length"]:
                    if self.strict_mode:
                        raise YAMLValidationError(
                            f"Field '{field_name}' is too long: maximum {field_spec['max_length']} characters",
                            field_name=field_name,
                            field_value=value,
                            file_path=source_file,
                        )
                    warnings.append(f"{field_name} too long")
            
            # 检查列表项数
            if isinstance(value, list):
                if "min_items" in field_spec and len(value) < field_spec["min_items"]:
                    if self.strict_mode:
                        raise YAMLValidationError(
                            f"Field '{field_name}' has too few items: minimum {field_spec['min_items']}",
                            field_name=field_name,
                            field_value=value,
                            file_path=source_file,
                        )
                    warnings.append(f"{field_name} has too few items")
                
                # 检查列表项模式
                if "item_pattern" in field_spec:
                    item_pattern = field_spec["item_pattern"]
                    for item in value:
                        if not isinstance(item, str):
                            if self.strict_mode:
                                raise YAMLValidationError(
                                    f"List item in '{field_name}' must be string",
                                    field_name=field_name,
                                    field_value=item,
                                    file_path=source_file,
                                )
                            warnings.append(f"Non-string item in {field_name}")
                            continue
                        
                        if not re.match(item_pattern, item):
                            if self.strict_mode:
                                raise YAMLValidationError(
                                    f"List item '{item}' in '{field_name}' does not match pattern: {item_pattern}",
                                    field_name=field_name,
                                    field_value=item,
                                    file_path=source_file,
                                )
                            warnings.append(f"Invalid item format in {field_name}: {item}")
    
    def _validate_optional_fields(
        self,
        frontmatter: dict,
        source_file: Optional[Path],
        warnings: list[str],
    ) -> None:
        """
        验证可选字段。
        
        Args:
            frontmatter: Frontmatter 字典
            source_file: 源文件路径
            warnings: 警告列表
        """
        import re
        
        for field_name, field_spec in OPTIONAL_FIELDS.items():
            value = frontmatter.get(field_name)
            
            if value is None:
                continue
            
            # 检查类型
            expected_type = field_spec["type"]
            if isinstance(expected_type, tuple):
                # 允许多种类型
                if not isinstance(value, expected_type):
                    warnings.append(f"Wrong type for {field_name}")
                    continue
            else:
                if not isinstance(value, expected_type):
                    warnings.append(f"Wrong type for {field_name}: expected {expected_type.__name__}")
                    continue
            
            # 检查模式匹配
            if "pattern" in field_spec and isinstance(value, str):
                pattern = field_spec["pattern"]
                if not re.match(pattern, value):
                    warnings.append(f"Invalid format for {field_name}")
            
            # 检查数值范围
            if isinstance(value, (int, float)):
                if "min" in field_spec and value < field_spec["min"]:
                    warnings.append(f"{field_name} below minimum")
                if "max" in field_spec and value > field_spec["max"]:
                    warnings.append(f"{field_name} above maximum")
    
    def _extract_topology_hints(
        self,
        frontmatter: dict,
        warnings: list[str],
    ) -> dict:
        """
        提取拓扑提示。
        
        Args:
            frontmatter: Frontmatter 字典
            warnings: 警告列表
            
        Returns:
            dict: 拓扑提示字典
        """
        topology_hints = frontmatter.get("topology_hints", {})
        
        if not topology_hints:
            return {}
        
        if not isinstance(topology_hints, dict):
            warnings.append("topology_hints must be a dictionary")
            return {}
        
        # 验证拓扑提示结构
        valid_hints: dict = {}
        
        # requires 列表
        if "requires" in topology_hints:
            requires = topology_hints["requires"]
            if isinstance(requires, list):
                valid_hints["requires"] = requires
            else:
                warnings.append("topology_hints.requires must be a list")
        
        # conflicts_with 列表
        if "conflicts_with" in topology_hints:
            conflicts = topology_hints["conflicts_with"]
            if isinstance(conflicts, list):
                valid_hints["conflicts_with"] = conflicts
            else:
                warnings.append("topology_hints.conflicts_with must be a list")
        
        # enhances 列表
        if "enhances" in topology_hints:
            enhances = topology_hints["enhances"]
            if isinstance(enhances, list):
                valid_hints["enhances"] = enhances
            else:
                warnings.append("topology_hints.enhances must be a list")
        
        # substitutes 列表
        if "substitutes" in topology_hints:
            substitutes = topology_hints["substitutes"]
            if isinstance(substitutes, list):
                valid_hints["substitutes"] = substitutes
            else:
                warnings.append("topology_hints.substitutes must be a list")
        
        return valid_hints
    
    def validate_skill_id(self, skill_id: str) -> bool:
        """
        验证技能 ID 格式。
        
        Args:
            skill_id: 技能 ID
            
        Returns:
            bool: 是否有效
        """
        import re
        return bool(re.match(REQUIRED_FIELDS["skill_id"]["pattern"], skill_id))
    
    def validate_version(self, version: str) -> bool:
        """
        验证版本号格式。
        
        Args:
            version: 版本号
            
        Returns:
            bool: 是否有效
        """
        import re
        return bool(re.match(REQUIRED_FIELDS["version"]["pattern"], version))
    
    def validate_permission(self, permission: str) -> bool:
        """
        验证权限声明格式。
        
        Args:
            permission: 权限声明
            
        Returns:
            bool: 是否有效
        """
        import re
        return bool(re.match(REQUIRED_FIELDS["permissions"]["item_pattern"], permission))