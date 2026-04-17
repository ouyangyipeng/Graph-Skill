# RFC-02: 离线图谱构建管道

**文档编号:** RFC-02  
**版本:** 2.0.0
**状态:** 正式发布
**最后更新:** 2026-04-17
**作者:** GraphSkill Architecture Team  
**分类:** 架构规范 - 离线处理  
**依赖:** RFC-00, RFC-01, RFC-08

---

## 目录

1. [概述](#1-概述)
2. [管道架构总览](#2-管道架构总览)
3. [文件监听与触发机制](#3-文件监听与触发机制)
4. [AST 解析引擎](#4-ast-解析引擎)
5. [静态校验引擎](#5-静态校验引擎)
6. [自动化拓扑边抽取引擎](#6-自动化拓扑边抽取引擎)
7. [DAG 约束校验](#7-dag-约束校验)
8. [批量导入策略](#8-批量导入策略)
9. [增量更新机制](#9-增量更新机制)
10. [错误处理与容错策略](#10-错误处理与容错策略)
11. [版本历史](#11-版本历史)

---

## 1. 概述

### 1.1 文档目的

本文档定义 GraphSkill 系统的离线图谱构建管道（Ingestion Pipeline），涵盖文件监听机制、AST 解析引擎、静态校验引擎、自动化拓扑边抽取算法、DAG 约束校验、批量导入策略、增量更新机制以及错误处理策略。

### 1.2 适用范围

本文档适用于：
- 后端开发工程师：实现 Ingestion Engine 各模块
- 数据工程师：设计数据导入流程
- DevOps 工程师：配置 Git Hook 与文件监听
- 技能库维护者：理解技能文件导入规范

### 1.3 设计原则

| 原则 | 描述 |
|------|------|
| **严格校验** | 所有导入数据 MUST 经过完整的静态校验，不合格数据 MUST 拒收 |
| **拓扑完整性** | 导入后 MUST 保证 REQUIRES 子图无环路，CONFLICTS_WITH 边对称 |
| **可追溯性** | 所有导入操作 MUST 记录审计日志，支持回滚 |
| **异步处理** | 大批量导入 SHOULD 采用异步批处理，避免阻塞主流程 |
| **边真实性** | REQUIRES 边 MUST 基于实际项目依赖关系（非人工猜测）；CONFLICTS_WITH 边覆盖度 MUST ≥ 10 pairs；技能规模 MUST ≥ 200 |

---

## 2. 管道架构总览

### 2.1 管道流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Ingestion Pipeline Architecture                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐                                                            │
│  │  Trigger    │  文件系统监听 / Git Hook / 手动触发                         │
│  │  Sources    │                                                            │
│  └──────┬──────┘                                                            │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                    │
│  │  File       │────▶│  AST        │────▶│  Static     │                    │
│  │  Reader     │     │  Parser     │     │  Validator  │                    │
│  │             │     │ (Tree-sitter)│     │             │                    │
│  └─────────────┘     └─────────────┘     └──────┬──────┘                    │
│                                                 │                           │
│                                                 ▼                           │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                    │
│  │  Embedding  │◀────│  Topology   │◀────│  DAG        │                    │
│  │  Generator  │     │  Extractor  │     │  Validator  │                    │
│  │             │     │ (LLM-based) │     │             │                    │
│  └─────────────┘     └─────────────┘     └──────┬──────┘                    │
│         │                                       │                           │
│         ▼                                       ▼                           │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                    │
│  │  Dual-Write │────▶│  Graph-     │────▶│  Audit      │                    │
│  │  Manager    │     │  Vector     │     │  Logger     │                    │
│  │             │     │  Store      │     │             │                    │
│  └─────────────┘     └─────────────┘     └─────────────┘                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责定义

| 模块 | 职责 | 输入 | 输出 |
|------|------|------|------|
| **File Reader** | 读取技能文件内容 | 文件路径 | 原始 Markdown 文本 |
| **AST Parser** | 解析 Markdown 结构 | 原始文本 | AST 节点树 |
| **Static Validator** | 校验 Schema 合规性 | AST 节点 | 校验结果 + 提取数据 |
| **DAG Validator** | 检测依赖环路 | 拓扑关系 | DAG 校验结果 |
| **Topology Extractor** | 推演隐性拓扑关系 | 技能描述 + 现有图谱 | 新边关系 |
| **Embedding Generator** | 生成向量嵌入 | 意图描述 | 向量数据 |
| **Dual-Write Manager** | 执行双写事务 | 节点/边数据 | 写入结果 |
| **Audit Logger** | 记录审计日志 | 操作记录 | 日志条目 |

### 2.3 处理模式

系统 MUST 支持两种处理模式：

| 模式 | 触发方式 | 处理策略 | 适用场景 |
|------|----------|----------|----------|
| **实时模式** | Git Hook / 单文件监听 | 立即处理，同步返回结果 | 开发调试、单技能更新 |
| **批处理模式** | 定时任务 / 手动触发 | 异步队列，批量处理 | 大规模导入、初始化 |

---

## 3. 文件监听与触发机制

### 3.1 触发源定义

系统 MUST 支持以下触发源：

| 触发源 | 类型 | 描述 | 配置方式 |
|--------|------|------|----------|
| **FileSystem Watcher** | 自动 | 监听指定目录的文件变更 | 配置监听路径 |
| **Git Hook** | 自动 | Git push/pre-commit 触发 | 配置 Git Hook 脚本 |
| **Manual Trigger** | 手动 | API 调用或 CLI 命令触发 | 调用 `/v1/ingest` API |
| **Scheduled Job** | 自动 | 定时扫描指定目录 | 配置 Cron 表达式 |

### 3.2 FileSystem Watcher 配置

```yaml
# config/file_watcher.yaml
file_watcher:
  enabled: true
  watch_paths:
    - "/data/skills"
    - "/data/skill_library"
  file_patterns:
    - "*.md"
    - "SKILL.md"
  exclude_patterns:
    - "*.tmp"
    - "*.bak"
    - ".git/**"
  event_types:
    - "create"      # 新建文件
    - "modify"      # 文件修改
    - "delete"      # 文件删除（触发软删除）
  debounce_ms: 500  # 防抖延迟，避免重复触发
  max_queue_size: 1000
```

### 3.3 Git Hook 集成规范

系统 SHOULD 提供标准 Git Hook 脚本，支持自动触发导入：

```bash
#!/bin/bash
# .git/hooks/post-receive
# GraphSkill Ingestion Trigger

GRAPHSKILL_API="http://localhost:8080/v1/ingest"
REPO_PATH="/data/skills"

while read oldrev newrev refname; do
    # 获取变更文件列表
    changed_files=$(git diff --name-only $oldrev $newrev | grep -E 'SKILL\.md$')
    
    if [ -n "$changed_files" ]; then
        # 触发批量导入
        curl -X POST "$GRAPHSKILL_API/batch" \
            -H "Content-Type: application/json" \
            -d "{\"files\": [$(echo $changed_files | sed 's/ /\",\"/g' | sed 's/^/\"/;s/$/\"/')], \"repo_path\": \"$REPO_PATH\"}"
        
        echo "GraphSkill ingestion triggered for: $changed_files"
    fi
done
```

### 3.4 触发事件数据结构

所有触发事件 MUST 统一为以下数据结构：

```json
{
  "event_id": "evt_abc123",
  "event_type": "file_create|file_modify|file_delete|git_push|manual",
  "timestamp": "2026-04-12T10:00:00Z",
  "source": {
    "type": "filesystem|git_hook|api|scheduled",
    "path": "/data/skills/git/SKILL.md",
    "repo": "optional_repo_url",
    "commit": "optional_commit_hash"
  },
  "payload": {
    "file_path": "/data/skills/git/SKILL.md",
    "content": "optional_raw_content",
    "skill_id": "optional_known_skill_id"
  },
  "priority": "normal|high|low",
  "retry_count": 0
}
```

---

## 4. AST 解析引擎

### 4.1 Tree-sitter 解析器配置

系统 MUST 使用 Tree-sitter 构建 Markdown 解析器，确保工业级 AST 解析能力。

#### 4.1.1 Tree-sitter Grammar 配置

```python
# src/ingestion/ast_parser.py

import tree_sitter_markdown as tsm
from tree_sitter import Language, Parser

class MarkdownASTParser:
    """
    基于 Tree-sitter 的 Markdown AST 解析器。
    强制分离描述域与代码域，提取结构化元数据。
    """
    
    def __init__(self):
        self.language = Language(tsm.language())
        self.parser = Parser(self.language)
    
    def parse(self, content: str) -> dict:
        """
        解析 Markdown 内容，返回结构化 AST。
        
        Args:
            content: Markdown 文件原始内容
            
        Returns:
            dict: 包含 frontmatter、sections、code_blocks 的结构化数据
            
        Raises:
            ASTParseError: 解析失败时抛出
        """
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        
        result = {
            "frontmatter": None,
            "sections": [],
            "code_blocks": [],
            "raw_text": content
        }
        
        # 遍历 AST 节点
        for child in root_node.children:
            if child.type == "frontmatter":
                result["frontmatter"] = self._extract_frontmatter(child)
            elif child.type == "section":
                result["sections"].append(self._extract_section(child))
            elif child.type == "fenced_code_block":
                result["code_blocks"].append(self._extract_code_block(child))
        
        return result
    
    def _extract_frontmatter(self, node) -> dict:
        """提取 YAML Frontmatter"""
        yaml_content = node.text.decode("utf8").strip("---\n")
        try:
            import yaml
            return yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ASTParseError(f"Frontmatter YAML parse error: {e}")
    
    def _extract_section(self, node) -> dict:
        """提取 Markdown Section"""
        return {
            "level": self._get_heading_level(node),
            "title": self._get_heading_text(node),
            "content": node.text.decode("utf8"),
            "start_line": node.start_point[0],
            "end_line": node.end_point[0]
        }
    
    def _extract_code_block(self, node) -> dict:
        """提取代码块"""
        return {
            "language": self._get_code_language(node),
            "content": self._get_code_content(node),
            "start_line": node.start_point[0],
            "end_line": node.end_point[0]
        }
```

### 4.2 解析输出结构

AST 解析器 MUST 输出以下结构化数据：

```json
{
  "frontmatter": {
    "skill_id": "git:commit_changes",
    "version": "1.2.0",
    "intent_description": "...",
    "permissions": ["fs:read:/tmp", "..."],
    "topology_hints": {
      "requires": ["git:configure"],
      "conflicts_with": ["git:reset_hard"]
    }
  },
  "sections": [
    {
      "level": 1,
      "title": "Description",
      "content": "# Description\n执行 Git 提交操作...",
      "start_line": 15,
      "end_line": 25
    },
    {
      "level": 2,
      "title": "Usage",
      "content": "## Usage\n...",
      "start_line": 26,
      "end_line": 40
    }
  ],
  "code_blocks": [
    {
      "language": "bash",
      "content": "git commit -m \"$MESSAGE\"",
      "start_line": 42,
      "end_line": 45
    },
    {
      "language": "python",
      "content": "def commit_changes(message: str):\n    ...",
      "start_line": 47,
      "end_line": 55
    }
  ],
  "raw_text": "完整 Markdown 内容..."
}
```

### 4.3 描述域与代码域分离规范

系统 MUST 严格分离"描述域"与"代码/指令域"：

| 域 | 内容类型 | 处理方式 |
|----|----------|----------|
| **描述域** | Markdown 文本、Section 内容 | 用于生成 Embedding，注入上下文 |
| **代码域** | Fenced Code Block、内联代码 | 仅存储元数据，MUST NOT 在 GraphSkill 进程内执行 |

**分离逻辑：**
```python
def separate_domains(ast_result: dict) -> tuple:
    """
    分离描述域与代码域。
    
    Returns:
        tuple: (description_text, code_metadata)
    """
    # 描述域：所有 Section 内容拼接
    description_parts = []
    for section in ast_result["sections"]:
        # 移除代码块，仅保留文本
        text_content = re.sub(r'```[\s\S]*?```', '', section["content"])
        description_parts.append(text_content.strip())
    
    description_text = "\n\n".join(description_parts)
    
    # 代码域：提取代码块元数据
    code_metadata = []
    for code_block in ast_result["code_blocks"]:
        code_metadata.append({
            "language": code_block["language"],
            "line_count": code_block["end_line"] - code_block["start_line"] + 1,
            "start_line": code_block["start_line"],
            "has_execution_risk": self._check_execution_risk(code_block)
        })
    
    return description_text, code_metadata
```

### 4.4 代码块风险检测

系统 SHOULD 检测代码块中的潜在风险模式：

| 风险类型 | 检测模式 | 风险级别 |
|----------|----------|----------|
| **破坏性命令** | `rm -rf`, `delete`, `drop` | HIGH |
| **网络请求** | `curl`, `wget`, `http.request` | MEDIUM |
| **环境修改** | `export`, `setenv`, `chmod` | MEDIUM |
| **权限提升** | `sudo`, `su`, `chmod 777` | CRITICAL |
| **敏感数据** | `password`, `secret`, `token` | HIGH |

```python
RISK_PATTERNS = {
    "CRITICAL": [
        r"sudo\s+",
        r"chmod\s+777",
        r"rm\s+-rf\s+/",
    ],
    "HIGH": [
        r"rm\s+-rf",
        r"drop\s+(table|database)",
        r"delete\s+from",
        r"(password|secret|token|api_key)\s*=",
    ],
    "MEDIUM": [
        r"curl\s+",
        r"wget\s+",
        r"export\s+",
        r"http\.request",
    ]
}

def check_execution_risk(code_block: dict) -> dict:
    """
    检测代码块执行风险。
    
    Returns:
        dict: {risk_level: str, risk_types: list, has_risk: bool}
    """
    content = code_block["content"]
    detected_risks = []
    max_risk_level = "LOW"
    
    for level, patterns in RISK_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                detected_risks.append(pattern)
                if RISK_LEVELS[level] > RISK_LEVELS[max_risk_level]:
                    max_risk_level = level
    
    return {
        "risk_level": max_risk_level,
        "risk_types": detected_risks,
        "has_risk": max_risk_level != "LOW"
    }
```

---

## 5. 静态校验引擎

### 5.1 校验流程

静态校验 MUST 执行以下校验步骤：

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Schema     │────▶│  Field      │────▶│  Permission │────▶│  Reference  │
│  Validation │     │  Validation │     │  Validation │     │  Validation │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  [JSON Schema]      [类型/长度检查]     [权限格式检查]      [依赖ID存在性]
```

### 5.2 Schema 校验

系统 MUST 使用 JSON Schema 校验 Frontmatter 合规性：

```python
import jsonschema
from jsonschema import validate, ValidationError

SKILL_MANIFEST_SCHEMA = {
    # 参见 RFC-01 定义的完整 Schema
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["skill_id", "version", "intent_description", "permissions"],
    # ... 完整 Schema 定义
}

class StaticValidator:
    """
    静态校验引擎，执行 Schema、字段、权限、引用校验。
    """
    
    def validate_schema(self, frontmatter: dict) -> ValidationResult:
        """
        执行 JSON Schema 校验。
        
        Args:
            frontmatter: YAML Frontmatter 解析结果
            
        Returns:
            ValidationResult: 校验结果对象
            
        Raises:
            SchemaValidationError: Schema 不合规时抛出
        """
        try:
            validate(instance=frontmatter, schema=SKILL_MANIFEST_SCHEMA)
            return ValidationResult(valid=True, errors=[])
        except ValidationError as e:
            return ValidationResult(
                valid=False,
                errors=[{
                    "field": e.path[-1] if e.path else "root",
                    "message": e.message,
                    "validator": e.validator,
                    "expected": e.schema.get("description", "N/A")
                }]
            )
```

### 5.3 字段校验规则

| 字段 | 校验规则 | 错误码 |
|------|----------|--------|
| `skill_id` | 正则匹配 `^[a-z0-9_-]+:[a-z0-9_-]+$` | `INVALID_SKILL_ID_FORMAT` |
| `version` | SemVer 2.0.0 格式 | `INVALID_VERSION_FORMAT` |
| `intent_description` | 长度 50-500 字符 | `INTENT_DESC_LENGTH_INVALID` |
| `permissions` | 非空数组，每项符合权限格式 | `INVALID_PERMISSION_FORMAT` |
| `topology_hints.requires` | 每项为有效 skill_id 格式 | `INVALID_DEPENDENCY_ID` |

### 5.4 权限格式校验

权限声明 MUST 符合以下格式规范：

```python
PERMISSION_PATTERN = r"^[a-z]+:[a-z]+(:[a-zA-Z0-9_/-]+)?$"

VALID_RESOURCE_TYPES = ["fs", "net", "db", "exec", "env", "api"]
VALID_ACTIONS = {
    "fs": ["read", "write", "delete", "execute"],
    "net": ["connect", "listen"],
    "db": ["query", "execute", "admin"],
    "exec": ["run"],
    "env": ["read", "write", "delete"],
    "api": ["call", "admin"]
}

def validate_permission(permission: str) -> tuple:
    """
    校验单个权限声明格式。
    
    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    if not re.match(PERMISSION_PATTERN, permission):
        return False, f"Permission '{permission}' does not match required format"
    
    parts = permission.split(":")
    resource_type = parts[0]
    action = parts[1]
    
    if resource_type not in VALID_RESOURCE_TYPES:
        return False, f"Invalid resource type: {resource_type}"
    
    if action not in VALID_ACTIONS.get(resource_type, []):
        return False, f"Invalid action '{action}' for resource type '{resource_type}'"
    
    return True, None
```

### 5.5 引用完整性校验

对于 `topology_hints` 中声明的依赖关系，系统 SHOULD 校验引用完整性：

```python
def validate_references(self, frontmatter: dict, existing_skills: set) -> ValidationResult:
    """
    校验拓扑提示中引用的技能 ID 是否存在。
    
    Args:
        frontmatter: Frontmatter 数据
        existing_skills: 系统中已存在的 skill_id 集合
        
    Returns:
        ValidationResult: 校验结果
    """
    errors = []
    topology_hints = frontmatter.get("topology_hints", {})
    
    for relation_type in ["requires", "conflicts_with", "substitutes", "enhances"]:
        referenced_skills = topology_hints.get(relation_type, [])
        for skill_id in referenced_skills:
            if skill_id not in existing_skills:
                errors.append({
                    "field": f"topology_hints.{relation_type}",
                    "message": f"Referenced skill '{skill_id}' does not exist",
                    "error_code": "REFERENCE_NOT_FOUND",
                    "severity": "WARNING"  # 警告级别，不阻止导入
                })
    
    return ValidationResult(
        valid=len([e for e in errors if e["severity"] == "ERROR"]) == 0,
        errors=errors
    )
```

### 5.6 校验结果数据结构

```python
class ValidationResult:
    """
    校验结果数据结构。
    """
    
    def __init__(self, valid: bool, errors: list):
        self.valid = valid
        self.errors = errors
        self.warnings = [e for e in errors if e.get("severity") == "WARNING"]
        self.error_count = len([e for e in errors if e.get("severity") == "ERROR"])
    
    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "error_count": self.error_count
        }
```

---

## 6. 自动化拓扑边抽取引擎

### 6.1 设计理念

除人工在 Frontmatter 中声明的 `topology_hints` 外，系统 MUST 具备基于 LLM 的自动化关系图谱推演能力，以发现隐性拓扑关系。

### 6.2 推演触发策略

| 触发场景 | 处理策略 | 置信度阈值 |
|----------|----------|------------|
| 新技能注册 | 立即触发异步推演 Worker | 0.85 |
| 批量导入 | 批量触发推演，并行处理 | 0.85 |
| 定期巡检 | 每日扫描未推演技能 | 0.80 |
| 用户请求 | API 触发即时推演 | 0.90 |

### 6.3 LLM 推演 Prompt 模板

```python
TOPOLOGY_INFERENCE_PROMPT = """
你是一个技能关系分析专家。请分析以下技能与现有技能库之间的拓扑关系。

## 新技能信息
- ID: {new_skill_id}
- 描述: {new_skill_description}
- 权限: {new_skill_permissions}
- 已声明依赖: {declared_dependencies}

## 现有高频技能列表（Top 20）
{existing_skills_list}

## 任务
请分析新技能与现有技能之间的关系，输出以下 JSON 格式：

```json
{
  "relations": [
    {
      "source": "<skill_id>",
      "target": "<skill_id>",
      "relation": "REQUIRES|CONFLICTS_WITH|ENHANCES|SUBSTITUTES",
      "confidence": <0.0-1.0>,
      "reason": "<简短理由>"
    }
  ]
}
```

## 关系定义
- REQUIRES: 执行 source 技能前必须先执行 target 技能（硬依赖）
- CONFLICTS_WITH: source 和 target 技能逻辑互斥，不能同时执行
- ENHANCES: target 技能能提升 source 技能的执行成功率（软依赖）
- SUBSTITUTES: source 和 target 功能相似，可互相替代

## 输出要求
1. 仅输出置信度 > 0.7 的关系
2. 每个关系必须包含明确的理由
3. 不要重复已声明的依赖关系
4. 输出必须是合法的 JSON 格式
"""
```

### 6.4 推演算法实现

```python
class TopologyExtractor:
    """
    基于 LLM 的拓扑关系推演引擎。
    """
    
    def __init__(self, llm_client, graph_store):
        self.llm_client = llm_client
        self.graph_store = graph_store
        self.confidence_threshold = 0.85
    
    async def infer_relations(
        self,
        new_skill: dict,
        existing_skills: list
    ) -> list:
        """
        推演新技能与现有技能之间的拓扑关系。
        
        Args:
            new_skill: 新技能数据
            existing_skills: 现有高频技能列表
            
        Returns:
            list: 推演出的关系列表
        """
        # 构建 Prompt
        prompt = TOPOLOGY_INFERENCE_PROMPT.format(
            new_skill_id=new_skill["skill_id"],
            new_skill_description=new_skill["intent_description"],
            new_skill_permissions=new_skill["permissions"],
            declared_dependencies=new_skill.get("topology_hints", {}),
            existing_skills_list=self._format_existing_skills(existing_skills)
        )
        
        # 调用 LLM
        response = await self.llm_client.generate(
            prompt=prompt,
            model="gpt-4o",
            temperature=0.3,  # 低温度确保稳定输出
            max_tokens=2000
        )
        
        # 解析响应
        try:
            result = self._parse_llm_response(response)
            relations = result.get("relations", [])
            
            # 过滤低置信度关系
            filtered_relations = [
                r for r in relations
                if r["confidence"] >= self.confidence_threshold
            ]
            
            return filtered_relations
        except LLMResponseParseError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return []
    
    def _parse_llm_response(self, response: str) -> dict:
        """
        解析 LLM 响应，提取 JSON 结构。
        """
        # 提取 JSON 块
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接解析
            json_str = response
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise LLMResponseParseError(f"JSON parse error: {e}")
    
    def _format_existing_skills(self, skills: list) -> str:
        """
        格式化现有技能列表为 Prompt 输入。
        """
        formatted = []
        for skill in skills[:20]:  # 限制 Top 20
            formatted.append(
                f"- ID: {skill['skill_id']}\n"
                f"  描述: {skill['intent_description'][:100]}...\n"
                f"  权限: {', '.join(skill['permissions'][:3])}"
            )
        return "\n".join(formatted)
```

### 6.5 推演结果写入规范

推演出的关系 MUST 遵循以下写入规范：

| 条件 | 处理方式 |
|------|----------|
| 置信度 >= 0.85 | 自动写入图数据库，标记 `verified_by_human: false` |
| 置信度 0.70-0.85 | 写入候选边集合，等待人工审核 |
| 置信度 < 0.70 | 不写入，仅记录日志 |

```python
async def write_inferred_relations(self, relations: list, skill_id: str):
    """
    写入推演出的关系边。
    """
    for relation in relations:
        confidence = relation["confidence"]
        
        if confidence >= 0.85:
            # 自动写入
            await self.graph_store.create_edge(
                source=relation["source"],
                target=relation["target"],
                edge_type=relation["relation"],
                properties={
                    "confidence": confidence,
                    "reason": relation["reason"],
                    "verified_by_human": False,
                    "auto_discovered": True,
                    "created_at": datetime.utcnow()
                }
            )
            logger.info(f"Auto-created edge: {relation['source']} -> {relation['target']}")
        
        elif confidence >= 0.70:
            # 写入候选集合
            await self.graph_store.create_candidate_edge(
                source=relation["source"],
                target=relation["target"],
                edge_type=relation["relation"],
                properties={
                    "confidence": confidence,
                    "reason": relation["reason"],
                    "status": "pending_review"
                }
            )
            logger.info(f"Created candidate edge for review: {relation['source']} -> {relation['target']}")
```

---

## 7. DAG 约束校验

### 7.1 环路检测算法

系统 MUST 在每次图结构更新事务提交前执行环路检测，确保 REQUIRES 子图是有向无环图（DAG）。

#### 7.1.1 Tarjan 算法实现

```python
class DAGValidator:
    """
    DAG 约束校验器，使用 Tarjan 算法检测环路。
    """
    
    def __init__(self, graph_store):
        self.graph_store = graph_store
    
    async def validate_dag(self, skill_id: str = None) -> DAGValidationResult:
        """
        执行 DAG 校验。
        
        Args:
            skill_id: 可选，仅校验涉及该技能的子图
            
        Returns:
            DAGValidationResult: 校验结果
        """
        # 获取 REQUIRES 子图
        if skill_id:
            subgraph = await self._get_skill_subgraph(skill_id)
        else:
            subgraph = await self._get_full_requires_graph()
        
        # 执行环路检测
        cycles = self._detect_cycles_tarjan(subgraph)
        
        return DAGValidationResult(
            is_dag=len(cycles) == 0,
            cycles=cycles,
            checked_nodes=len(subgraph.nodes),
            checked_edges=len(subgraph.edges)
        )
    
    def _detect_cycles_tarjan(self, graph: nx.DiGraph) -> list:
        """
        使用 Tarjan 算法检测强连通分量（SCC）。
        若 SCC 包含多于 1 个节点，则存在环路。
        
        Args:
            graph: NetworkX 有向图
            
        Returns:
            list: 检测到的环路列表
        """
        import networkx as nx
        
        cycles = []
        sccs = list(nx.strongly_connected_components(graph))
        
        for scc in sccs:
            if len(scc) > 1:
                # SCC 包含多个节点，存在环路
                cycle_path = self._extract_cycle_path(graph, scc)
                cycles.append(cycle_path)
        
        return cycles
    
    def _extract_cycle_path(self, graph: nx.DiGraph, scc: set) -> list:
        """
        从强连通分量中提取环路路径。
        """
        import networkx as nx
        
        # 在 SCC 内寻找简单环路
        scc_graph = graph.subgraph(scc)
        try:
            cycle = nx.find_cycle(scc_graph)
            return [node for node, _ in cycle]
        except nx.NetworkXNoCycle:
            return list(scc)
    
    async def _get_skill_subgraph(self, skill_id: str) -> nx.DiGraph:
        """
        获取涉及指定技能的 REQUIRES 子图。
        """
        # Cypher 查询获取相关节点和边
        query = """
        MATCH (s:SkillNode {uid: $skill_id})
        CALL apoc.path.subgraphAll(s, {
            relationshipFilter: "REQUIRES>",
            maxDepth: 10
        })
        YIELD nodes, relationships
        RETURN nodes, relationships
        """
        result = await self.graph_store.execute_query(query, {"skill_id": skill_id})
        
        # 构建 NetworkX 图
        import networkx as nx
        graph = nx.DiGraph()
        
        for node in result["nodes"]:
            graph.add_node(node["uid"])
        
        for rel in result["relationships"]:
            graph.add_edge(
                rel["source"]["uid"],
                rel["target"]["uid"]
            )
        
        return graph
```

### 7.2 环路检测时机

系统 MUST 在以下时机执行环路检测：

| 时机 | 检测范围 | 失败处理 |
|------|----------|----------|
| 新建 REQUIRES 边 | 涉及该边的子图 | 拒绝写入，抛出异常 |
| 更新 REQUIRES 边 | 涉及该边的子图 | 拒绝更新，抛出异常 |
| 批量导入 | 全图 | 拒绝整个批次 |
| 定期巡检 | 全图 | 记录告警，通知管理员 |

### 7.3 TopologyCycleException 定义

```python
class TopologyCycleException(Exception):
    """
    拓扑环路异常。
    当 REQUIRES 子图检测到环路时抛出。
    """
    
    def __init__(self, cycle_path: list, operation: str):
        self.cycle_path = cycle_path
        self.operation = operation
        self.message = (
            f"REQUIRES subgraph contains cycle: {cycle_path}. "
            f"Operation '{operation}' rejected to prevent deadlock."
        )
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        return {
            "error_type": "TopologyCycleException",
            "cycle_path": self.cycle_path,
            "operation": self.operation,
            "message": self.message
        }
```

### 7.4 环路修复建议

当检测到环路时，系统 SHOULD 提供修复建议：

```python
def generate_cycle_fix_suggestions(self, cycle_path: list) -> list:
    """
    生成环路修复建议。
    
    Returns:
        list: 建议删除的边列表
    """
    suggestions = []
    
    # 分析环路中的每条边
    for i in range(len(cycle_path)):
        source = cycle_path[i]
        target = cycle_path[(i + 1) % len(cycle_path)]
        
        # 获取边的属性
        edge_props = self.graph_store.get_edge_properties(source, target, "REQUIRES")
        
        suggestions.append({
            "action": "delete_edge",
            "source": source,
            "target": target,
            "reason": f"Removing this edge breaks the cycle",
            "is_hard_dependency": edge_props.get("is_hard", True),
            "priority": "high" if edge_props.get("is_hard", True) else "medium"
        })
    
    # 按优先级排序
    suggestions.sort(key=lambda x: x["priority"], reverse=True)
    
    return suggestions
```

---

## 8. 批量导入策略

### 8.1 批量导入流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  1. 准备    │────▶│  2. 解析    │────▶│  3. 校验    │────▶│  4. 推演    │
│  (扫描文件) │     │  (批量AST)  │     │  (批量校验) │     │  (拓扑推演) │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  [文件列表]          [AST结果集]         [校验结果集]         [关系列表]
                                                                   │
                                                                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  8. 完成    │◀────│  7. 审计    │◀────│  6. 写入    │◀────│  5. DAG     │
│  (通知)     │     │  (日志)     │     │  (双写事务) │     │  (环路检测) │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### 8.2 批量导入配置

```yaml
# config/batch_import.yaml
batch_import:
  batch_size: 50          # 单批次处理技能数量
  parallel_workers: 4     # 并行 Worker 数量
  timeout_seconds: 300    # 单批次超时时间
  
  retry_policy:
    max_retries: 3
    retry_delay_seconds: 5
    exponential_backoff: true
  
  validation_mode: "strict"  # strict | lenient
  dag_check_mode: "full"     # full | partial
  
  progress_reporting:
    enabled: true
    report_interval_seconds: 10
    webhook_url: "optional_webhook_for_notifications"
```

### 8.3 批量导入 API

```python
class BatchImporter:
    """
    批量导入处理器。
    """
    
    async def import_batch(
        self,
        file_paths: list,
        config: BatchImportConfig
    ) -> BatchImportResult:
        """
        执行批量导入。
        
        Args:
            file_paths: 文件路径列表
            config: 导入配置
            
        Returns:
            BatchImportResult: 导入结果
        """
        result = BatchImportResult(
            total_files=len(file_paths),
            successful=0,
            failed=0,
            skipped=0,
            errors=[]
        )
        
        # 分批处理
        batches = self._split_into_batches(file_paths, config.batch_size)
        
        for batch_idx, batch in enumerate(batches):
            batch_result = await self._process_batch(batch, config, batch_idx)
            
            result.successful += batch_result.successful
            result.failed += batch_result.failed
            result.skipped += batch_result.skipped
            result.errors.extend(batch_result.errors)
            
            # 进度报告
            if config.progress_reporting.enabled:
                await self._report_progress(result, batch_idx, len(batches))
        
        return result
    
    async def _process_batch(
        self,
        batch: list,
        config: BatchImportConfig,
        batch_idx: int
    ) -> BatchResult:
        """
        处理单个批次。
        """
        # 并行解析
        ast_results = await self._parallel_parse(batch, config.parallel_workers)
        
        # 批量校验
        validation_results = await self._batch_validate(ast_results)
        
        # 过滤不合格数据
        valid_skills = [
            r for r in validation_results
            if r["validation"]["valid"]
        ]
        
        if not valid_skills:
            return BatchResult(
                successful=0,
                failed=len(batch),
                skipped=0,
                errors=[r["validation"]["errors"] for r in validation_results]
            )
        
        # 执行 DAG 校验（全图）
        dag_result = await self.dag_validator.validate_dag()
        if not dag_result.is_dag:
            raise TopologyCycleException(
                dag_result.cycles[0],
                f"batch_import_{batch_idx}"
            )
        
        # 执行拓扑推演
        await self._batch_infer_topology(valid_skills)
        
        # 执行双写
        write_results = await self._batch_dual_write(valid_skills)
        
        return BatchResult(
            successful=len(write_results["success"]),
            failed=len(write_results["failed"]),
            skipped=len(batch) - len(valid_skills),
            errors=write_results["errors"]
        )
```

### 8.4 批量导入结果数据结构

```json
{
  "import_id": "imp_abc123",
  "timestamp": "2026-04-12T10:00:00Z",
  "total_files": 150,
  "successful": 145,
  "failed": 3,
  "skipped": 2,
  "duration_seconds": 120,
  "errors": [
    {
      "file_path": "/data/skills/invalid/SKILL.md",
      "error_type": "SchemaValidationError",
      "error_message": "Missing required field: skill_id",
      "line_number": 5
    }
  ],
  "warnings": [
    {
      "file_path": "/data/skills/new/SKILL.md",
      "warning_type": "ReferenceNotFound",
      "warning_message": "Referenced skill 'git:configure' does not exist"
    }
  ]
}
```

---

## 9. 增量更新机制

### 9.1 增量更新场景

| 场景 | 触发方式 | 处理策略 |
|------|----------|----------|
| 技能内容修改 | File Watcher | 解析变更部分，更新节点属性 |
| 版本升级 | Git Hook | 创建新版本节点，标记旧版本 deprecated |
| 依赖关系变更 | API 调用 | 更新边属性，重新执行 DAG 校验 |
| 技能删除 | File Watcher | 软删除标记，保留历史数据 |

### 9.2 版本升级处理

```python
async def handle_version_upgrade(
    self,
    existing_skill_id: str,
    new_version: str,
    new_content: dict
) -> VersionUpgradeResult:
    """
    处理技能版本升级。
    
    流程：
    1. 创建新版本节点
    2. 标记旧版本为 deprecated
    3. 迁移边关系到新版本
    4. 更新向量嵌入
    """
    # 获取旧版本节点
    old_node = await self.graph_store.get_node(existing_skill_id)
    
    # 创建新版本节点
    new_skill_id = f"{existing_skill_id.split(':')[0]}:{existing_skill_id.split(':')[1]}@{new_version}"
    
    # 双写新版本
    await self.dual_write_manager.write_skill({
        "skill_id": new_skill_id,
        "version": new_version,
        **new_content
    })
    
    # 标记旧版本 deprecated
    await self.graph_store.update_node(
        existing_skill_id,
        {"is_deprecated": True, "deprecated_reason": "version_upgrade"}
    )
    
    # 迁移边关系
    await self._migrate_edges(existing_skill_id, new_skill_id)
    
    return VersionUpgradeResult(
        old_skill_id=existing_skill_id,
        new_skill_id=new_skill_id,
        success=True
    )
```

### 9.3 边关系迁移

```python
async def _migrate_edges(self, old_skill_id: str, new_skill_id: str):
    """
    迁移边关系到新版本节点。
    """
    # 获取所有关联边
    edges = await self.graph_store.get_node_edges(old_skill_id)
    
    for edge in edges:
        # 创建新边
        if edge["source"] == old_skill_id:
            await self.graph_store.create_edge(
                source=new_skill_id,
                target=edge["target"],
                edge_type=edge["type"],
                properties=edge["properties"]
            )
        elif edge["target"] == old_skill_id:
            await self.graph_store.create_edge(
                source=edge["source"],
                target=new_skill_id,
                edge_type=edge["type"],
                properties=edge["properties"]
            )
    
    # 保留旧边但标记为 legacy
    await self.graph_store.update_edges(
        old_skill_id,
        {"is_legacy": True, "migrated_to": new_skill_id}
    )
```

---

## 10. 错误处理与容错策略

### 10.1 错误分类

| 错误类型 | 错误码 | 处理策略 |
|----------|--------|----------|
| **解析错误** | `AST_PARSE_ERROR` | 记录日志，跳过文件 |
| **Schema 错误** | `SCHEMA_VALIDATION_ERROR` | 记录详细错误，跳过文件 |
| **DAG 环路** | `TOPOLOGY_CYCLE_ERROR` | 拒绝整个批次 |
| **双写失败** | `DUAL_WRITE_ERROR` | 触发补偿删除 |
| **LLM 调用失败** | `LLM_INFERENCE_ERROR` | 重试 3 次，降级为人工审核 |

### 10.2 错误处理流程

```python
class IngestionErrorHandler:
    """
    导入错误处理器。
    """
    
    async def handle_error(
        self,
        error: Exception,
        context: dict
    ) -> ErrorHandlingResult:
        """
        处理导入过程中的错误。
        
        Args:
            error: 异常对象
            context: 错误上下文（文件路径、批次信息等）
            
        Returns:
            ErrorHandlingResult: 处理结果
        """
        error_type = self._classify_error(error)
        
        handlers = {
            "AST_PARSE_ERROR": self._handle_parse_error,
            "SCHEMA_VALIDATION_ERROR": self._handle_schema_error,
            "TOPOLOGY_CYCLE_ERROR": self._handle_cycle_error,
            "DUAL_WRITE_ERROR": self._handle_write_error,
            "LLM_INFERENCE_ERROR": self._handle_llm_error
        }
        
        handler = handlers.get(error_type, self._handle_unknown_error)
        return await handler(error, context)
    
    async def _handle_parse_error(self, error, context) -> ErrorHandlingResult:
        """
        处理 AST 解析错误。
        """
        # 记录详细日志
        await self.audit_logger.log_error({
            "error_type": "AST_PARSE_ERROR",
            "file_path": context["file_path"],
            "error_message": str(error),
            "timestamp": datetime.utcnow()
        })
        
        # 跳过该文件，继续处理其他文件
        return ErrorHandlingResult(
            action="skip",
            retry=False,
            message=f"Skipped file due to parse error: {context['file_path']}"
        )
    
    async def _handle_cycle_error(self, error, context) -> ErrorHandlingResult:
        """
        处理 DAG 环路错误。
        """
        # 拒绝整个批次
        await self.audit_logger.log_error({
            "error_type": "TOPOLOGY_CYCLE_ERROR",
            "batch_id": context["batch_id"],
            "cycle_path": error.cycle_path,
            "timestamp": datetime.utcnow()
        })
        
        # 生成修复建议
        suggestions = self.dag_validator.generate_cycle_fix_suggestions(error.cycle_path)
        
        return ErrorHandlingResult(
            action="reject_batch",
            retry=False,
            message=f"Batch rejected due to cycle: {error.cycle_path}",
            suggestions=suggestions
        )
    
    async def _handle_write_error(self, error, context) -> ErrorHandlingResult:
        """
        处理双写错误。
        """
        # 触发补偿删除
        if context.get("vector_id"):
            await self.compensation_manager.trigger_compensation({
                "vector_id": context["vector_id"],
                "skill_id": context["skill_id"],
                "reason": "dual_write_failed"
            })
        
        # 重试（最多 3 次）
        if context.get("retry_count", 0) < 3:
            return ErrorHandlingResult(
                action="retry",
                retry=True,
                retry_delay=5 * (context.get("retry_count", 0) + 1)
            )
        
        return ErrorHandlingResult(
            action="skip",
            retry=False,
            message=f"Skipped after 3 retries: {context['skill_id']}"
        )
```

### 10.3 补偿删除机制

```python
class CompensationManager:
    """
    补偿删除管理器，处理双写失败后的数据清理。
    """
    
    async def trigger_compensation(self, payload: dict):
        """
        触发补偿删除消息。
        """
        message = {
            "message_type": "compensation_delete",
            "target": "vector_db",
            "vector_id": payload["vector_id"],
            "skill_id": payload["skill_id"],
            "reason": payload["reason"],
            "timestamp": datetime.utcnow().isoformat(),
            "retry_count": 0,
            "max_retries": 3
        }
        
        # 发送到 Kafka
        await self.kafka_producer.send(
            topic="graphskill_compensation",
            key=payload["skill_id"],
            value=json.dumps(message).encode()
        )
    
    async def execute_compensation(self, message: dict) -> bool:
        """
        执行补偿删除。
        """
        try:
            await self.vector_store.delete_vector(message["vector_id"])
            logger.info(f"Compensation delete successful: {message['vector_id']}")
            return True
        except Exception as e:
            logger.error(f"Compensation delete failed: {e}")
            
            # 重试
            if message["retry_count"] < message["max_retries"]:
                message["retry_count"] += 1
                await self.trigger_compensation(message)
            
            return False
```

---

## 11. 版本历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| 1.0.0 | 2026-04-12 | 初始版本发布 | GraphSkill Architecture Team |
| 2.0.0 | 2026-04-17 | **VR-First 架构适配**：新增边真实性设计原则（REQUIRES 基于实际依赖、CONFLICTS ≥ 10 pairs、技能规模 ≥ 200）；适配 1-hop expansion 约束 | GraphSkill Architecture Team |

---

**文档结束**

*本文档定义了 GraphSkill 系统的离线图谱构建管道。相关数据结构定义详见 [RFC-08: 数据结构与 Schema 定义](RFC-08-data-structures-schema.md)，存储层规范详见 [RFC-01: 数据规范与存储层设计](RFC-01-data-specification-storage-layer.md)。*