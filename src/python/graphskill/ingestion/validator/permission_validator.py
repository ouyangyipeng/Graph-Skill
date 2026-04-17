"""
权限声明校验器。

验证 SKILL.md 文件中的权限声明是否符合规范。

Reference: RFC-01 Section 2.4, RFC-11
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from graphskill.core.exceptions import IngestionError


class PermissionCategory(str, Enum):
    """权限类别。"""
    
    FS = "fs"          # 文件系统
    NET = "net"        # 网络
    DB = "db"          # 数据库
    EXEC = "exec"      # 执行命令
    ENV = "env"        # 环境变量
    SECRET = "secret"  # 密钥/敏感信息
    AGENT = "agent"    # Agent 控制
    SYSTEM = "system"  # 系统操作
    CUSTOM = "custom"  # 自定义权限


class PermissionAction(str, Enum):
    """权限动作。"""
    
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    LIST = "list"
    CREATE = "create"
    UPDATE = "update"
    CONNECT = "connect"
    HTTP = "http"
    HTTPS = "https"
    SSH = "ssh"
    QUERY = "query"
    ADMIN = "admin"


@dataclass
class PermissionInfo:
    """解析后的权限信息。"""
    
    category: str
    action: str
    target: Optional[str] = None
    raw_permission: str = ""
    is_valid: bool = True
    validation_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "action": self.action,
            "target": self.target,
            "raw_permission": self.raw_permission,
            "is_valid": self.is_valid,
            "validation_message": self.validation_message,
        }


@dataclass
class PermissionValidationResult:
    """权限验证结果。"""
    
    is_valid: bool
    permissions: list[PermissionInfo] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    high_risk_permissions: list[PermissionInfo] = field(default_factory=list)
    
    @property
    def permission_count(self) -> int:
        """权限数量。"""
        return len(self.permissions)
    
    @property
    def high_risk_count(self) -> int:
        """高风险权限数量。"""
        return len(self.high_risk_permissions)
    
    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "permission_count": self.permission_count,
            "high_risk_count": self.high_risk_count,
            "permissions": [p.to_dict() for p in self.permissions],
            "errors": self.errors,
            "warnings": self.warnings,
            "high_risk_permissions": [p.to_dict() for p in self.high_risk_permissions],
        }


class PermissionValidationError(IngestionError):
    """权限验证错误。
    
    Error Code: GS-2012
    """
    
    def __init__(
        self,
        message: str,
        permissions: Optional[list[PermissionInfo]] = None,
        file_path: Optional[Path] = None,
    ):
        super().__init__(message)
        self.code = "GS-2012"
        self.permissions = permissions or []
        self.file_path = file_path
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        result["permissions"] = [p.to_dict() for p in self.permissions]
        if self.file_path:
            result["file_path"] = str(self.file_path)
        return result


# 权限格式正则表达式
PERMISSION_PATTERN = r"^[a-z]+:[a-z]+(:[a-zA-Z0-9_/.-]+)?$"

# 高风险权限定义
HIGH_RISK_PERMISSIONS = {
    # 文件系统高风险
    "fs:delete:/",           # 删除任意文件
    "fs:write:/",            # 写入任意位置
    "fs:execute:/",          # 执行任意文件
    
    # 网络高风险
    "net:connect:*",         # 连接任意地址
    "net:http:*",            # HTTP 请求任意地址
    
    # 执行高风险
    "exec:execute:*",        # 执行任意命令
    "exec:admin:*",          # 管理员命令
    
    # 系统高风险
    "system:admin",          # 系统管理员权限
    "system:shutdown",       # 系统关机
    
    # 密钥高风险
    "secret:read:*",         # 读取任意密钥
    "secret:write:*",        # 写入任意密钥
}

# 权限类别与允许的动作映射
PERMITTED_ACTIONS = {
    "fs": ["read", "write", "delete", "execute", "list", "create"],
    "net": ["connect", "http", "https", "ssh", "list"],
    "db": ["query", "read", "write", "delete", "create", "update", "admin"],
    "exec": ["execute", "list"],
    "env": ["read", "write", "list"],
    "secret": ["read", "write", "list"],
    "agent": ["control", "query", "configure"],
    "system": ["info", "configure", "admin", "shutdown"],
}

# 权限目标格式规范
TARGET_FORMATS = {
    "fs": r"^/[a-zA-Z0-9_/.-]*$",           # 文件路径格式
    "net": r"^[a-zA-Z0-9.-]+(:\d+)?$",      # 主机名/域名格式
    "db": r"^[a-zA-Z0-9_-]+$",              # 数据库名格式
    "exec": r"^[a-zA-Z0-9_/-]+$",           # 命令格式
    "env": r"^[A-Z_][A-Z0-9_]*$",           # 环境变量名格式
    "secret": r"^[a-zA-Z0-9_-]+$",          # 密钥名格式
}


class PermissionValidator:
    """
    权限声明校验器。
    
    验证权限声明是否符合规范格式。
    
    Features:
        - 格式验证
        - 类别验证
        - 动作验证
        - 高风险权限检测
        - 目标格式验证
    
    Example:
        >>> validator = PermissionValidator()
        >>> result = validator.validate(["fs:read:/tmp", "net:http:github.com"])
        >>> if not result.is_valid:
        ...     for error in result.errors:
        ...         print(error)
    """
    
    def __init__(self, strict_mode: bool = True):
        """
        初始化校验器。
        
        Args:
            strict_mode: 严格模式，启用时对验证失败抛出异常
        """
        self.strict_mode = strict_mode
    
    def validate(
        self,
        permissions: list[str],
        file_path: Optional[Path] = None,
    ) -> PermissionValidationResult:
        """
        验证权限列表。
        
        Args:
            permissions: 权限声明列表
            file_path: 源文件路径
            
        Returns:
            PermissionValidationResult: 验证结果
            
        Raises:
            PermissionValidationError: 验证失败（严格模式）
        """
        import re
        
        parsed_permissions: list[PermissionInfo] = []
        errors: list[str] = []
        warnings: list[str] = []
        high_risk_permissions: list[PermissionInfo] = []
        
        for permission in permissions:
            # 解析权限
            info = self._parse_permission(permission)
            parsed_permissions.append(info)
            
            # 验证格式
            if not info.is_valid:
                errors.append(info.validation_message or f"Invalid permission: {permission}")
                continue
            
            # 检查高风险权限
            if self._is_high_risk(info):
                high_risk_permissions.append(info)
                warnings.append(f"High-risk permission detected: {permission}")
            
            # 验证动作是否允许
            if not self._is_action_permitted(info):
                warnings.append(f"Unusual action '{info.action}' for category '{info.category}'")
            
            # 验证目标格式
            if info.target and not self._is_target_valid(info):
                warnings.append(f"Target '{info.target}' may not follow expected format for '{info.category}'")
        
        result = PermissionValidationResult(
            is_valid=len(errors) == 0,
            permissions=parsed_permissions,
            errors=errors,
            warnings=warnings,
            high_risk_permissions=high_risk_permissions,
        )
        
        if self.strict_mode and not result.is_valid:
            raise PermissionValidationError(
                f"Permission validation failed with {len(errors)} errors",
                permissions=parsed_permissions,
                file_path=file_path,
            )
        
        return result
    
    def _parse_permission(self, permission: str) -> PermissionInfo:
        """
        解析权限声明。
        
        Args:
            permission: 权限声明字符串
            
        Returns:
            PermissionInfo: 解析结果
        """
        import re
        
        # 检查基本格式
        if not re.match(PERMISSION_PATTERN, permission):
            return PermissionInfo(
                category="",
                action="",
                raw_permission=permission,
                is_valid=False,
                validation_message=f"Permission '{permission}' does not match format 'category:action[:target]'",
            )
        
        # 分解权限
        parts = permission.split(":")
        category = parts[0]
        action = parts[1]
        target = parts[2] if len(parts) > 2 else None
        
        return PermissionInfo(
            category=category,
            action=action,
            target=target,
            raw_permission=permission,
            is_valid=True,
        )
    
    def _is_high_risk(self, info: PermissionInfo) -> bool:
        """
        检查是否为高风险权限。
        
        Args:
            info: 权限信息
            
        Returns:
            bool: 是否高风险
        """
        # 构建权限模式
        permission = info.raw_permission
        
        # 检查精确匹配
        if permission in HIGH_RISK_PERMISSIONS:
            return True
        
        # 检查通配符匹配
        # 高风险模式：category:action:* 或 category:action:/ (fs)
        if info.target == "*" or info.target == "/":
            return True
        
        # 检查特定高风险动作
        high_risk_actions = {
            "fs": ["delete", "execute"],
            "exec": ["execute"],
            "system": ["admin", "shutdown"],
            "secret": ["read", "write"],
        }
        
        if info.category in high_risk_actions:
            if info.action in high_risk_actions[info.category]:
                # 如果没有限制目标，视为高风险
                if not info.target or info.target in ("*", "/", "all"):
                    return True
        
        return False
    
    def _is_action_permitted(self, info: PermissionInfo) -> bool:
        """
        检查动作是否在允许范围内。
        
        Args:
            info: 权限信息
            
        Returns:
            bool: 动作是否允许
        """
        permitted = PERMITTED_ACTIONS.get(info.category, [])
        
        # 如果类别不在预定义列表中，允许任意动作（自定义权限）
        if not permitted:
            return True
        
        return info.action in permitted
    
    def _is_target_valid(self, info: PermissionInfo) -> bool:
        """
        检查目标格式是否正确。
        
        Args:
            info: 权限信息
            
        Returns:
            bool: 目标格式是否正确
        """
        import re
        
        if not info.target:
            return True
        
        # 获取目标格式
        target_pattern = TARGET_FORMATS.get(info.category)
        
        if not target_pattern:
            # 未知类别，允许任意目标
            return True
        
        return bool(re.match(target_pattern, info.target))
    
    def validate_file(
        self,
        file_path: Path,
        permissions: Optional[list[str]] = None,
    ) -> PermissionValidationResult:
        """
        验证文件中的权限声明。
        
        Args:
            file_path: 技能文件路径
            permissions: 可选的权限列表（如果未提供，将解析文件）
            
        Returns:
            PermissionValidationResult: 验证结果
        """
        import yaml
        import re
        
        if permissions is None:
            if not file_path.exists():
                return PermissionValidationResult(
                    is_valid=False,
                    errors=[f"File not found: {file_path}"],
                )
            
            try:
                content = file_path.read_text(encoding="utf-8")
                
                # 提取 Frontmatter
                pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
                match = pattern.match(content)
                
                if not match:
                    return PermissionValidationResult(
                        is_valid=False,
                        errors=["No valid YAML frontmatter found"],
                    )
                
                yaml_content = match.group(1)
                frontmatter = yaml.safe_load(yaml_content)
                
                if not isinstance(frontmatter, dict):
                    return PermissionValidationResult(
                        is_valid=False,
                        errors=["Frontmatter must be a YAML dictionary"],
                    )
                
                permissions = frontmatter.get("permissions", [])
                
                if not permissions:
                    return PermissionValidationResult(
                        is_valid=False,
                        errors=["No permissions declared in frontmatter"],
                    )
            
            except yaml.YAMLError as e:
                return PermissionValidationResult(
                    is_valid=False,
                    errors=[f"YAML parsing error: {e}"],
                )
            except Exception as e:
                return PermissionValidationResult(
                    is_valid=False,
                    errors=[f"File reading error: {e}"],
                )
        
        return self.validate(permissions, file_path)
    
    def get_permission_summary(
        self,
        permissions: list[str],
    ) -> dict:
        """
        获取权限摘要。
        
        Args:
            permissions: 权限列表
            
        Returns:
            dict: 权限摘要
        """
        result = self.validate(permissions)
        
        # 按类别分组
        by_category: dict[str, list[str]] = {}
        for info in result.permissions:
            if info.category not in by_category:
                by_category[info.category] = []
            by_category[info.category].append(info.raw_permission)
        
        return {
            "total_count": result.permission_count,
            "high_risk_count": result.high_risk_count,
            "categories": list(by_category.keys()),
            "by_category": by_category,
            "is_valid": result.is_valid,
        }
    
    def check_permission_conflict(
        self,
        permissions_a: list[str],
        permissions_b: list[str],
    ) -> list[dict]:
        """
        检查两组权限之间的冲突。
        
        Args:
            permissions_a: 第一组权限
            permissions_b: 第二组权限
            
        Returns:
            list: 冲突列表
        """
        conflicts: list[dict] = []
        
        # 解析两组权限
        parsed_a = [self._parse_permission(p) for p in permissions_a]
        parsed_b = [self._parse_permission(p) for p in permissions_b]
        
        # 检查读写冲突
        for info_a in parsed_a:
            for info_b in parsed_b:
                # 同类别同目标的读写冲突
                if info_a.category == info_b.category and info_a.target == info_b.target:
                    # 读-删除冲突
                    if (info_a.action == "read" and info_b.action == "delete") or \
                       (info_a.action == "delete" and info_b.action == "read"):
                        conflicts.append({
                            "type": "read_delete_conflict",
                            "permission_a": info_a.raw_permission,
                            "permission_b": info_b.raw_permission,
                            "message": f"Read and delete on same target '{info_a.target}'",
                        })
                    
                    # 写-执行冲突
                    if (info_a.action == "write" and info_b.action == "execute") or \
                       (info_a.action == "execute" and info_b.action == "write"):
                        conflicts.append({
                            "type": "write_execute_conflict",
                            "permission_a": info_a.raw_permission,
                            "permission_b": info_b.raw_permission,
                            "message": f"Write and execute on same target '{info_a.target}'",
                        })
        
        return conflicts
    
    def is_permission_format_valid(self, permission: str) -> bool:
        """
        检查权限格式是否有效。
        
        Args:
            permission: 权限声明
            
        Returns:
            bool: 格式是否有效
        """
        import re
        return bool(re.match(PERMISSION_PATTERN, permission))