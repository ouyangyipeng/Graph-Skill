# RFC-04: Agent 运行时接入层

**文档编号:** RFC-04  
**版本:** 1.0.0  
**状态:** 正式发布  
**最后更新:** 2026-04-12  
**作者:** GraphSkill Architecture Team  
**分类:** 架构规范 - 运行时集成  
**依赖:** RFC-00, RFC-03, RFC-07, RFC-11

---

## 目录

1. [概述](#1-概述)
2. [接入层架构总览](#2-接入层架构总览)
3. [技能注入中间件协议](#3-技能注入中间件协议)
4. [输出规范与上下文外壳](#4-输出规范与上下文外壳)
5. [细粒度权限拦截器](#5-细粒度权限拦截器)
6. [会话管理机制](#6-会话管理机制)
7. [Agent 框架集成规范](#7-agent-框架集成规范)
8. [Tool Call JSON Schema](#8-tool-call-json-schema)
9. [错误处理与异常传递](#9-错误处理与异常传递)
10. [版本历史](#10-版本历史)

---

## 1. 概述

### 1.1 文档目的

本文档定义 GraphSkill 系统的 Agent 运行时接入层（Runtime Integration Layer），涵盖技能注入中间件协议、输出规范、细粒度权限拦截器、会话管理机制、与主流 Agent 框架的集成规范、Tool Call JSON Schema 以及错误处理策略。

### 1.2 适用范围

本文档适用于：
- Agent 框架开发者：集成 GraphSkill 路由能力
- 后端开发工程师：实现权限拦截器与会话管理
- 安全工程师：设计权限校验流程
- Agent 应用开发者：理解技能注入机制

### 1.3 设计原则

| 原则 | 描述 |
|------|------|
| **职责分离** | GraphSkill 不负责 Agent 执行逻辑，只提供标准化上下文外壳 |
| **权限强制校验** | Agent 调用技能 MUST 经过权限拦截器校验 |
| **框架中立** | 输出格式 MUST 兼容主流 Agent 框架 |
| **安全隔离** | 技能代码 MUST NOT 在 GraphSkill 进程内执行 |

### 1.4 系统边界定义

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GraphSkill Runtime Integration Boundary                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Agent System (外部)                           │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │   │
│  │  │ LLM Brain   │  │ Executor    │  │ Sandbox (技能代码执行)       │  │   │
│  │  │             │  │             │  │                             │  │   │
│  │  └───────┬─────┘  └───────┬─────┘  └─────────────┬───────────────┘  │   │
│  │          │                │                      │                  │   │
│  └──────────┼────────────────┼──────────────────────┼──────────────────┘   │
│             │                │                      │                       │
│             │  请求技能上下文 │                      │ 执行结果反馈           │
│             │                │                      │                       │
│             ▼                ▼                      ▼                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     GraphSkill Runtime Layer                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Context     │  │ Permission  │  │ Session     │  │ Telemetry   │ │   │
│  │  │ Provider    │  │ Interceptor │  │ Manager     │  │ Tracer      │ │   │
│  │  │             │  │             │  │             │  │             │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  │         │                │                │                │        │   │
│  │         ▼                ▼                ▼                ▼        │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │                   Routing Gateway (核心路由)                  │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**职责边界说明：**

| 职责 | GraphSkill 负责 | Agent 系统负责 |
|------|------------------|----------------|
| 技能上下文组装 | ✅ | ❌ |
| 权限校验 | ✅ | ❌ |
| 技能代码执行 | ❌ | ✅ |
| LLM 推理调用 | ❌ | ✅ |
| 执行结果处理 | ❌ | ✅ |
| 遥测数据收集 | ✅ | ✅（配合） |

---

## 2. 接入层架构总览

### 2.1 模块架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Runtime Integration Architecture                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Integration Interface Layer                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ LangChain   │  │ AutoGen     │  │ OpenDevin   │  │ Custom      │ │   │
│  │  │ Adapter     │  │ Adapter     │  │ Adapter     │  │ Adapter     │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Middleware Layer                                 │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Context     │  │ Permission  │  │ Session     │  │ Telemetry   │ │   │
│  │  │ Injection   │  │ Interceptor │  │ Manager     │  │ Middleware  │ │   │
│  │  │ Middleware  │  │             │  │             │  │             │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Output Assembly Layer                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ XML         │  │ JSON        │  │ Tool Call   │  │ Prompt      │ │   │
│  │  │ Assembler   │  │ Assembler   │  │ Schema Gen  │  │ Template    │ │   │
│  │  │             │  │             │  │             │  │ Engine      │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Core Routing Gateway                             │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │              Hybrid Retrieval + Conflict Pruning              │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责定义

| 模块 | 职责 | 输入 | 输出 |
|------|------|------|------|
| **Framework Adapter** | 适配不同 Agent 框架的接口差异 | 框架特定请求 | 标准化请求 |
| **Context Injection Middleware** | 将技能上下文注入 Agent Prompt | 路由结果 | 注入后的 Prompt |
| **Permission Interceptor** | 校验技能调用权限 | Action 请求 | 校验结果 |
| **Session Manager** | 管理 Agent 会话状态 | Session 操作 | 状态更新 |
| **Telemetry Middleware** | 收集执行遥测数据 | 执行事件 | 遥测记录 |
| **Output Assembler** | 组装输出格式 | 路由结果 | 格式化输出 |

---

## 3. 技能注入中间件协议

### 3.1 注入流程规范

技能注入 MUST 遵循以下流程：

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Agent      │────▶│  Routing    │────▶│  Context    │────▶│  Prompt     │
│  Request    │     │  Gateway    │     │  Assembly   │     │  Injection  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  [Query + Context]   [Skill List]        [Formatted Context]  [Final Prompt]
```

### 3.2 注入时机规范

技能注入 MUST 在以下时机执行：

| 时机 | 触发条件 | 注入策略 |
|------|----------|----------|
| **初始化注入** | Agent Session 创建时 | 注入基础技能集 |
| **任务触发注入** | 用户 Query 到达时 | 动态路由注入 |
| **补充注入** | Agent 请求额外技能时 | 补充路由注入 |
| **错误恢复注入** | Agent 执行失败时 | 注入错误处理技能 |

### 3.3 注入位置规范

技能上下文 MUST 注入到 Agent Prompt 的特定位置：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Agent Prompt Structure                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ [System Prompt]                                                      │   │
│  │ "You are an AI assistant with the following capabilities..."         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ [Injected Skills Context] ← GraphSkill 注入位置                      │   │
│  │ <SystemSkills>                                                        │   │
│  │   <Skill id="...">...</Skill>                                         │   │
│  │ </SystemSkills>                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ [User Query]                                                          │   │
│  │ "Please help me commit the code changes..."                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ [Conversation History]                                                │   │
│  │ Previous messages...                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.4 注入中间件实现

```python
class ContextInjectionMiddleware:
    """
    技能上下文注入中间件。
    """
    
    def __init__(self, routing_gateway, config: InjectionConfig):
        self.routing_gateway = routing_gateway
        self.config = config
    
    async def inject(
        self,
        agent_prompt: AgentPrompt,
        query: str,
        context_state: dict,
        max_tokens: int
    ) -> InjectedPrompt:
        """
        执行技能上下文注入。
        
        Args:
            agent_prompt: Agent 原始 Prompt 结构
            query: 用户查询
            context_state: 当前上下文状态
            max_tokens: Token 预算
            
        Returns:
            InjectedPrompt: 注入后的 Prompt
        """
        # Step 1: 调用路由网关获取技能
        routing_result = await self.routing_gateway.route(
            query=query,
            context_state=context_state,
            max_tokens=max_tokens - self._get_base_prompt_tokens(agent_prompt)
        )
        
        # Step 2: 组装技能上下文
        skills_context = await self._assemble_skills_context(routing_result)
        
        # Step 3: 注入到指定位置
        injected_prompt = self._inject_at_position(
            agent_prompt,
            skills_context,
            self.config.injection_position
        )
        
        # Step 4: 记录注入日志
        await self._log_injection(injected_prompt, routing_result)
        
        return InjectedPrompt(
            original_prompt=agent_prompt,
            injected_context=skills_context,
            final_prompt=injected_prompt,
            routing_result=routing_result,
            token_count=self._count_tokens(injected_prompt)
        )
    
    async def _assemble_skills_context(
        self,
        routing_result: RoutingResult
    ) -> str:
        """
        组装技能上下文文本。
        """
        assembler = XMLAssembler()
        return assembler.assemble(routing_result)
    
    def _inject_at_position(
        self,
        prompt: AgentPrompt,
        context: str,
        position: str
    ) -> str:
        """
        在指定位置注入上下文。
        """
        if position == "after_system":
            return f"{prompt.system_prompt}\n\n{context}\n\n{prompt.user_query}"
        elif position == "before_query":
            return f"{prompt.system_prompt}\n\n{context}\n\n{prompt.user_query}"
        else:
            # 默认：注入到 System Prompt 后
            return f"{prompt.system_prompt}\n\n{context}\n\n{prompt.user_query}"
    
    def _get_base_prompt_tokens(self, prompt: AgentPrompt) -> int:
        """
        计算基础 Prompt Token 数。
        """
        tokenizer = tiktoken.get_encoding("cl100k_base")
        base_text = f"{prompt.system_prompt}\n\n{prompt.user_query}"
        return len(tokenizer.encode(base_text))
```

### 3.5 注入配置规范

```yaml
# config/injection.yaml
injection:
  position: "after_system"  # after_system | before_query | custom
  
  # Token 预算分配
  token_budget:
    system_prompt_reserved: 500
    conversation_history_reserved: 1000
    skills_context_max: 4000
    
  # 注入策略
  strategy:
    mode: "dynamic"  # dynamic | static | hybrid
    refresh_on_query: true
    cache_injected_context: true
    
  # 格式配置
  format:
    type: "xml"  # xml | json | markdown
    include_permissions: true
    include_dependencies: true
```

---

## 4. 输出规范与上下文外壳

### 4.1 XML 输出格式规范

系统 MUST 支持以 XML 标签包裹的输出格式：

```xml
<SystemSkills 
  xmlns="https://graphskill.io/schemas/system-skills-v1"
  token_count="2850"
  routing_mode="normal"
  session_id="sess_abc123"
  timestamp="2026-04-12T10:00:00Z">
  
  <Meta>
    <QueryHash>sha256:abc123...</QueryHash>
    <RoutingLatencyMs>285</RoutingLatencyMs>
    <CacheHit>false</CacheHit>
  </Meta>
  
  <Skill id="git:configure" priority="1" type="required">
    <Description>配置 Git 用户信息，设置 name 和 email</Description>
    <Instructions>
      执行以下命令配置 Git：
      1. git config --global user.name "$NAME"
      2. git config --global user.email "$EMAIL"
    </Instructions>
    <Permissions>
      <Permission resource="exec" action="run" target="git"/>
      <Permission resource="env" action="write" target="GIT_AUTHOR_NAME"/>
    </Permissions>
    <Dependencies>
      <Requires skill_id="env:check_git_installed"/>
    </Dependencies>
    <Metadata>
      <Version>1.2.0</Version>
      <Author>graphskill-team</Author>
      <SuccessRate>0.98</SuccessRate>
    </Metadata>
  </Skill>
  
  <Skill id="git:commit_changes" priority="2" type="seed" requires="git:configure">
    <Description>执行 Git 提交操作，将当前工作区的变更提交到本地仓库</Description>
    <Instructions>
      1. 检查是否有未暂存的文件：git status
      2. 暂存变更：git add -A
      3. 提交：git commit -m "$MESSAGE"
    </Instructions>
    <Permissions>
      <Permission resource="fs" action="read" target="/"/>
      <Permission resource="exec" action="run" target="git"/>
    </Permissions>
    <ToolCallSchema>
      {
        "name": "git_commit",
        "parameters": {
          "message": {"type": "string", "required": true}
        }
      }
    </ToolCallSchema>
  </Skill>
  
  <Skill id="git:push_remote" priority="3" type="enhances">
    <Description>推送本地提交到远程仓库</Description>
    <Instructions>
      执行 git push origin $BRANCH
    </Instructions>
    <ToolCallSchema>
      {
        "name": "git_push",
        "parameters": {
          "branch": {"type": "string", "default": "main"}
        }
      }
    </ToolCallSchema>
  </Skill>
  
</SystemSkills>
```

### 4.2 JSON 输出格式规范

系统 MUST 支持以 JSON 格式的输出：

```json
{
  "system_skills": {
    "meta": {
      "token_count": 2850,
      "routing_mode": "normal",
      "session_id": "sess_abc123",
      "timestamp": "2026-04-12T10:00:00Z",
      "routing_latency_ms": 285
    },
    "skills": [
      {
        "id": "git:configure",
        "priority": 1,
        "type": "required",
        "description": "配置 Git 用户信息，设置 name 和 email",
        "instructions": "执行以下命令配置 Git...",
        "permissions": [
          {"resource": "exec", "action": "run", "target": "git"},
          {"resource": "env", "action": "write", "target": "GIT_AUTHOR_NAME"}
        ],
        "dependencies": {
          "requires": ["env:check_git_installed"]
        },
        "metadata": {
          "version": "1.2.0",
          "author": "graphskill-team",
          "success_rate": 0.98
        }
      },
      {
        "id": "git:commit_changes",
        "priority": 2,
        "type": "seed",
        "requires": "git:configure",
        "description": "执行 Git 提交操作...",
        "instructions": "1. 检查是否有未暂存的文件...",
        "permissions": [
          {"resource": "fs", "action": "read", "target": "/"},
          {"resource": "exec", "action": "run", "target": "git"}
        ],
        "tool_call_schema": {
          "name": "git_commit",
          "parameters": {
            "message": {"type": "string", "required": true}
          }
        }
      }
    ]
  }
}
```

### 4.3 输出组装器实现

```python
class OutputAssembler:
    """
    输出组装器，支持多种输出格式。
    """
    
    def __init__(self, config: OutputConfig):
        self.config = config
        self.assemblers = {
            "xml": XMLAssembler(),
            "json": JSONAssembler(),
            "markdown": MarkdownAssembler()
        }
    
    def assemble(
        self,
        routing_result: RoutingResult,
        format_type: str = "xml"
    ) -> str:
        """
        组装输出内容。
        
        Args:
            routing_result: 路由结果
            format_type: 输出格式类型
            
        Returns:
            str: 格式化后的输出内容
        """
        assembler = self.assemblers.get(format_type)
        if not assembler:
            raise UnsupportedFormatError(f"Unsupported format: {format_type}")
        
        return assembler.assemble(routing_result)


class XMLAssembler:
    """
    XML 格式组装器。
    """
    
    def assemble(self, routing_result: RoutingResult) -> str:
        """
        组装 XML 格式输出。
        """
        xml_parts = []
        
        # 头部
        xml_parts.append(
            f'<SystemSkills token_count="{routing_result.token_count}" '
            f'routing_mode="{routing_result.routing_mode}" '
            f'session_id="{routing_result.session_id}">'
        )
        
        # Meta 信息
        xml_parts.append('<Meta>')
        xml_parts.append(f'<RoutingLatencyMs>{routing_result.latency_ms}</RoutingLatencyMs>')
        xml_parts.append('</Meta>')
        
        # 技能列表
        for skill in routing_result.skills:
            xml_parts.append(self._assemble_skill(skill))
        
        xml_parts.append('</SystemSkills>')
        
        return '\n'.join(xml_parts)
    
    def _assemble_skill(self, skill: SkillData) -> str:
        """
        组装单个技能 XML。
        """
        parts = []
        parts.append(
            f'<Skill id="{skill.skill_id}" priority="{skill.priority}" type="{skill.type}">'
        )
        parts.append(f'<Description>{skill.description}</Description>')
        parts.append(f'<Instructions>{skill.instructions}</Instructions>')
        
        # 权限
        parts.append('<Permissions>')
        for perm in skill.permissions:
            parts.append(
                f'<Permission resource="{perm["resource"]}" '
                f'action="{perm["action"]}" target="{perm["target"]}"/>'
            )
        parts.append('</Permissions>')
        
        # Tool Call Schema
        if skill.tool_call_schema:
            parts.append('<ToolCallSchema>')
            parts.append(json.dumps(skill.tool_call_schema, indent=2))
            parts.append('</ToolCallSchema>')
        
        parts.append('</Skill>')
        
        return '\n'.join(parts)


class JSONAssembler:
    """
    JSON 格式组装器。
    """
    
    def assemble(self, routing_result: RoutingResult) -> str:
        """
        组装 JSON 格式输出。
        """
        output = {
            "system_skills": {
                "meta": {
                    "token_count": routing_result.token_count,
                    "routing_mode": routing_result.routing_mode,
                    "session_id": routing_result.session_id,
                    "routing_latency_ms": routing_result.latency_ms
                },
                "skills": [
                    {
                        "id": skill.skill_id,
                        "priority": skill.priority,
                        "type": skill.type,
                        "description": skill.description,
                        "instructions": skill.instructions,
                        "permissions": skill.permissions,
                        "tool_call_schema": skill.tool_call_schema
                    }
                    for skill in routing_result.skills
                ]
            }
        }
        
        return json.dumps(output, indent=2)
```

### 4.4 上下文外壳接口定义

系统 MUST 提供标准化的上下文外壳接口：

```python
class ContextShell:
    """
    标准化上下文外壳，封装技能上下文与元数据。
    """
    
    def __init__(
        self,
        skills: List[SkillData],
        meta: ShellMeta,
        permissions: PermissionSet,
        tool_calls: List[ToolCallDefinition]
    ):
        self.skills = skills
        self.meta = meta
        self.permissions = permissions
        self.tool_calls = tool_calls
    
    def to_xml(self) -> str:
        """
        转换为 XML 格式。
        """
        return XMLAssembler().assemble(self._to_routing_result())
    
    def to_json(self) -> str:
        """
        转换为 JSON 格式。
        """
        return JSONAssembler().assemble(self._to_routing_result())
    
    def to_prompt_section(self) -> str:
        """
        转换为 Prompt Section 格式。
        """
        return MarkdownAssembler().assemble(self._to_routing_result())
    
    def get_tool_definitions(self) -> List[dict]:
        """
        获取 Tool Call 定义列表（用于 OpenAI Function Calling）。
        """
        return [tc.to_openai_format() for tc in self.tool_calls]
    
    def validate_permission(self, action: ActionRequest) -> bool:
        """
        校验 Action 是否在权限范围内。
        """
        return self.permissions.check(action)


class ShellMeta:
    """
    上下文外壳元数据。
    """
    
    token_count: int
    routing_mode: str
    session_id: str
    timestamp: str
    routing_latency_ms: int
    query_hash: str
    cache_hit: bool


class SkillData:
    """
    技能数据结构。
    """
    
    skill_id: str
    priority: int
    type: str  # seed | required | enhances
    description: str
    instructions: str
    permissions: List[dict]
    dependencies: List[str]
    tool_call_schema: dict
    metadata: dict
```

---

## 5. 细粒度权限拦截器

### 5.1 权限拦截流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Agent      │────▶│  Action     │────▶│  Permission │────▶│  Execution  │
│  Decision   │     │  Request    │     │  Interceptor│     │  (if passed)│
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  [Tool Call]        [Action 解析]        [权限校验]          [执行/拒绝]
```

### 5.2 权限校验逻辑

```python
class PermissionInterceptor:
    """
    细粒度权限拦截器，校验 Agent 调用的技能权限。
    """
    
    def __init__(self, graph_store, session_manager):
        self.graph_store = graph_store
        self.session_manager = session_manager
    
    async def intercept(
        self,
        action_request: ActionRequest,
        session_id: str
    ) -> InterceptionResult:
        """
        拦截并校验 Action 请求。
        
        Args:
            action_request: Agent 发起的 Action 请求
            session_id: 当前 Session ID
            
        Returns:
            InterceptionResult: 拦截结果（通过/拒绝）
        """
        # Step 1: 解析 Action
        parsed_action = self._parse_action(action_request)
        
        # Step 2: 获取技能权限声明
        skill_permissions = await self._get_skill_permissions(parsed_action.skill_id)
        
        # Step 3: 获取 Session 授权范围
        session_authorization = await self.session_manager.get_authorization(session_id)
        
        # Step 4: 执行权限校验
        validation_result = self._validate_permissions(
            parsed_action,
            skill_permissions,
            session_authorization
        )
        
        # Step 5: 检查技能是否在当前上下文中
        context_check = await self._check_skill_in_context(
            parsed_action.skill_id,
            session_id
        )
        
        # 综合判断
        if not validation_result.valid:
            return InterceptionResult(
                allowed=False,
                reason=f"Permission denied: {validation_result.reason}",
                error_code="PERMISSION_DENIED"
            )
        
        if not context_check.in_context:
            return InterceptionResult(
                allowed=False,
                reason=f"Skill '{parsed_action.skill_id}' not in current context",
                error_code="SKILL_NOT_IN_CONTEXT"
            )
        
        return InterceptionResult(
            allowed=True,
            reason="Permission check passed",
            skill_id=parsed_action.skill_id,
            action=parsed_action
        )
    
    def _parse_action(self, request: ActionRequest) -> ParsedAction:
        """
        解析 Action 请求，提取技能 ID 和操作详情。
        """
        # 从 Tool Call 中解析技能 ID
        tool_name = request.tool_call.get("name", "")
        
        # 技能 ID 映射（tool_name -> skill_id）
        skill_id = self._map_tool_to_skill(tool_name)
        
        # 提取操作参数
        parameters = request.tool_call.get("parameters", {})
        
        return ParsedAction(
            skill_id=skill_id,
            tool_name=tool_name,
            parameters=parameters,
            resource_type=self._infer_resource_type(parameters),
            action_type=self._infer_action_type(tool_name)
        )
    
    async def _get_skill_permissions(self, skill_id: str) -> List[Permission]:
        """
        从图数据库获取技能声明的权限。
        """
        query = """
        MATCH (s:SkillNode {uid: $skill_id})
        RETURN s.permissions as permissions
        """
        result = await self.graph_store.execute_query(query, {"skill_id": skill_id})
        
        if not result:
            return []
        
        permissions = result[0].get("permissions", [])
        return [self._parse_permission(p) for p in permissions]
    
    def _parse_permission(self, perm_str: str) -> Permission:
        """
        解析权限字符串为 Permission 对象。
        """
        parts = perm_str.split(":")
        return Permission(
            resource_type=parts[0],
            action=parts[1],
            target=parts[2] if len(parts) > 2 else "*"
        )
    
    def _validate_permissions(
        self,
        action: ParsedAction,
        skill_permissions: List[Permission],
        session_auth: SessionAuthorization
    ) -> ValidationResult:
        """
        执行权限校验。
        
        校验规则：
        1. Action 必须在技能声明的权限范围内
        2. 技能权限必须在 Session 授权范围内
        """
        # 检查 Action 是否匹配技能权限
        action_matched = False
        for perm in skill_permissions:
            if self._match_permission(action, perm):
                action_matched = True
                break
        
        if not action_matched:
            return ValidationResult(
                valid=False,
                reason=f"Action '{action.action_type}' on '{action.resource_type}' "
                       f"not declared in skill permissions"
            )
        
        # 检查技能权限是否在 Session 授权范围内
        for perm in skill_permissions:
            if not self._check_session_authorization(perm, session_auth):
                return ValidationResult(
                    valid=False,
                    reason=f"Skill permission '{perm}' exceeds session authorization"
                )
        
        return ValidationResult(valid=True)
    
    def _match_permission(self, action: ParsedAction, permission: Permission) -> bool:
        """
        检查 Action 是否匹配权限声明。
        """
        # 资源类型匹配
        if action.resource_type != permission.resource_type:
            return False
        
        # 动作匹配
        if action.action_type != permission.action:
            return False
        
        # 目标匹配（支持通配符）
        if permission.target == "*":
            return True
        
        # 精确匹配或路径前缀匹配
        if action.parameters.get("target") == permission.target:
            return True
        
        # 路径前缀匹配（如 fs:read:/tmp 匹配 /tmp/xxx）
        if permission.resource_type == "fs" and permission.target.endswith("*"):
            prefix = permission.target.rstrip("*")
            if action.parameters.get("path", "").startswith(prefix):
                return True
        
        return False
    
    async def _check_skill_in_context(
        self,
        skill_id: str,
        session_id: str
    ) -> ContextCheckResult:
        """
        检查技能是否在当前 Session 的上下文中。
        """
        context = await self.session_manager.get_current_context(session_id)
        
        if skill_id in context.skills:
            return ContextCheckResult(in_context=True)
        
        return ContextCheckResult(
            in_context=False,
            reason=f"Skill '{skill_id}' was not loaded in current routing context"
        )
```

### 5.3 权限校验数据结构

```python
class ActionRequest:
    """
    Agent 发起的 Action 请求。
    """
    
    tool_call: dict          # Tool Call JSON
    session_id: str          # Session ID
    timestamp: str           # 请求时间
    request_id: str          # 请求唯一 ID


class ParsedAction:
    """
    解析后的 Action。
    """
    
    skill_id: str            # 技能 ID
    tool_name: str           # Tool 名称
    parameters: dict         # 参数
    resource_type: str       # 资源类型（fs/net/db/exec/env）
    action_type: str         # 动作类型（read/write/delete/run）


class Permission:
    """
    权限声明。
    """
    
    resource_type: str       # 资源类型
    action: str              # 动作
    target: str              # 目标（路径/域名/命令）


class SessionAuthorization:
    """
    Session 授权范围。
    """
    
    session_id: str
    authorized_permissions: List[Permission]
    authorized_skills: List[str]
    expires_at: str


class InterceptionResult:
    """
    拦截结果。
    """
    
    allowed: bool            # 是否允许执行
    reason: str              # 原因说明
    error_code: str          # 错误码（拒绝时）
    skill_id: str            # 技能 ID
    action: ParsedAction     # 解析后的 Action
```

### 5.4 权限拒绝处理

当权限校验失败时，系统 MUST 返回标准化错误响应：

```python
class PermissionDeniedError:
    """
    权限拒绝错误响应。
    """
    
    def __init__(
        self,
        skill_id: str,
        action: ParsedAction,
        reason: str,
        error_code: str
    ):
        self.skill_id = skill_id
        self.action = action
        self.reason = reason
        self.error_code = error_code
    
    def to_agent_response(self) -> dict:
        """
        转换为 Agent 可理解的响应格式。
        """
        return {
            "error": {
                "type": "permission_denied",
                "code": self.error_code,
                "message": self.reason,
                "skill_id": self.skill_id,
                "action": {
                    "tool_name": self.action.tool_name,
                    "resource_type": self.action.resource_type,
                    "action_type": self.action.action_type
                },
                "suggestion": self._generate_suggestion()
            }
        }
    
    def _generate_suggestion(self) -> str:
        """
        生成修复建议。
        """
        if self.error_code == "PERMISSION_DENIED":
            return f"Request additional permission: {self.action.resource_type}:{self.action.action_type}"
        elif self.error_code == "SKILL_NOT_IN_CONTEXT":
            return f"Request skill '{self.skill_id}' to be loaded into context"
        else:
            return "Review skill permissions and session authorization"
```

---

## 6. 会话管理机制

### 6.1 Session 数据结构

```python
class AgentSession:
    """
    Agent Session 数据结构。
    """
    
    session_id: str                    # Session 唯一 ID
    agent_id: str                      # Agent 实例 ID
    created_at: str                    # 创建时间
    expires_at: str                    # 过期时间
    
    # 上下文状态
    current_context: SessionContext    # 当前技能上下文
    context_history: List[dict]        # 上下文变更历史
    
    # 授权信息
    authorization: SessionAuthorization # Session 授权范围
    
    # 执行状态
    execution_state: ExecutionState    # 执行状态
    skill_call_history: List[dict]     # 技能调用历史
    
    # 元数据
    metadata: dict                     # Session 元数据


class SessionContext:
    """
    Session 技能上下文。
    """
    
    skills: List[str]                  # 当前加载的技能 ID
    routing_mode: str                  # 路由模式
    last_routing_time: str             # 最后路由时间
    token_count: int                   # 当前 Token 数
    query_hash: str                    # 最后 Query 哈希


class ExecutionState:
    """
    执行状态。
    """
    
    status: str                        # idle | executing | waiting | error
    current_skill: str                 # 当前执行的技能
    pending_actions: List[dict]        # 待执行 Action
    error_history: List[dict]          # 错误历史
```

### 6.2 Session Manager 实现

```python
class SessionManager:
    """
    Session 管理器，管理 Agent 会话状态。
    """
    
    def __init__(self, redis_client, config: SessionConfig):
        self.redis = redis_client
        self.config = config
        self.session_ttl = config.session_ttl  # 默认 24 小时
    
    async def create_session(
        self,
        agent_id: str,
        authorization: SessionAuthorization
    ) -> AgentSession:
        """
        创建新 Session。
        
        Args:
            agent_id: Agent 实例 ID
            authorization: Session 授权范围
            
        Returns:
            AgentSession: 新创建的 Session
        """
        session_id = self._generate_session_id()
        
        session = AgentSession(
            session_id=session_id,
            agent_id=agent_id,
            created_at=datetime.utcnow().isoformat(),
            expires_at=(datetime.utcnow() + timedelta(hours=24)).isoformat(),
            current_context=SessionContext(
                skills=[],
                routing_mode="none",
                last_routing_time=None,
                token_count=0,
                query_hash=None
            ),
            context_history=[],
            authorization=authorization,
            execution_state=ExecutionState(
                status="idle",
                current_skill=None,
                pending_actions=[],
                error_history=[]
            ),
            skill_call_history=[],
            metadata={}
        )
        
        # 存储到 Redis
        await self._store_session(session)
        
        return session
    
    async def get_session(self, session_id: str) -> Optional[AgentSession]:
        """
        获取 Session。
        """
        session_data = await self.redis.get(f"session:{session_id}")
        
        if session_data:
            return AgentSession.from_json(session_data)
        
        return None
    
    async def update_context(
        self,
        session_id: str,
        new_context: SessionContext
    ) -> AgentSession:
        """
        更新 Session 上下文。
        """
        session = await self.get_session(session_id)
        
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")
        
        # 记录历史
        session.context_history.append({
            "previous_context": session.current_context.to_dict(),
            "new_context": new_context.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # 更新当前上下文
        session.current_context = new_context
        
        # 存储更新
        await self._store_session(session)
        
        return session
    
    async def record_skill_call(
        self,
        session_id: str,
        skill_call: dict
    ) -> None:
        """
        记录技能调用。
        """
        session = await self.get_session(session_id)
        
        if session:
            session.skill_call_history.append({
                "skill_id": skill_call["skill_id"],
                "action": skill_call["action"],
                "status": skill_call["status"],
                "timestamp": datetime.utcnow().isoformat()
            })
            
            await self._store_session(session)
    
    async def get_authorization(
        self,
        session_id: str
    ) -> SessionAuthorization:
        """
        获取 Session 授权范围。
        """
        session = await self.get_session(session_id)
        
        if session:
            return session.authorization
        
        return SessionAuthorization(
            session_id=session_id,
            authorized_permissions=[],
            authorized_skills=[],
            expires_at=None
        )
    
    async def get_current_context(
        self,
        session_id: str
    ) -> SessionContext:
        """
        获取当前上下文。
        """
        session = await self.get_session(session_id)
        
        if session:
            return session.current_context
        
        return SessionContext(
            skills=[],
            routing_mode="none",
            last_routing_time=None,
            token_count=0,
            query_hash=None
        )
    
    async def terminate_session(self, session_id: str) -> None:
        """
        终止 Session。
        """
        await self.redis.delete(f"session:{session_id}")
    
    def _generate_session_id(self) -> str:
        """
        生成 Session ID。
        """
        import uuid
        return f"sess_{uuid.uuid4().hex[:16]}"
    
    async def _store_session(self, session: AgentSession) -> None:
        """
        存储 Session 到 Redis。
        """
        await self.redis.setex(
            f"session:{session.session_id}",
            self.session_ttl,
            session.to_json()
        )
```

### 6.3 Session 配置规范

```yaml
# config/session.yaml
session:
  ttl_seconds: 86400  # 24 小时
  
  # 上下文历史
  context_history:
    max_entries: 100
    retention_seconds: 3600
  
  # 技能调用历史
  skill_call_history:
    max_entries: 500
    retention_seconds: 7200
  
  # 并发控制
  concurrency:
    max_sessions_per_agent: 10
    max_total_sessions: 10000
  
  # 清理策略
  cleanup:
    enabled: true
    interval_seconds: 300
    expired_session_cleanup: true
```

---

## 7. Agent 框架集成规范

### 7.1 LangChain 集成适配器

```python
class LangChainAdapter:
    """
    LangChain 框架集成适配器。
    """
    
    def __init__(self, graphskill_client):
        self.client = graphskill_client
    
    def create_skill_retriever(self) -> "SkillRetriever":
        """
        创建 LangChain 兼容的技能检索器。
        """
        from langchain.tools import Tool
        
        class SkillRetriever:
            """
            LangChain 技能检索器，作为 Tool 使用。
            """
            
            name = "graphskill_retriever"
            description = "Retrieve relevant skills based on query"
            
            def __init__(self, client):
                self.client = client
            
            async def _arun(self, query: str, run_manager=None):
                """
                异步执行技能检索。
                """
                result = await self.client.route_skills(
                    query=query,
                    context_state={},
                    max_tokens=4000
                )
                
                # 转换为 LangChain Tool 格式
                tools = []
                for skill in result["skills"]:
                    tools.append(Tool(
                        name=skill["id"],
                        description=skill["description"],
                        func=self._create_skill_function(skill)
                    ))
                
                return tools
            
            def _create_skill_function(self, skill: dict):
                """
                创建技能执行函数。
                """
                def skill_func(*args, **kwargs):
                    # 返回技能指令，实际执行由 Agent 负责
                    return skill["instructions"]
                
                return skill_func
        
        return SkillRetriever(self.client)
    
    def create_context_injector(self) -> "ContextInjector":
        """
        创建 LangChain 兼容的上下文注入器。
        """
        class ContextInjector:
            """
            LangChain 上下文注入器，作为 Runnable 使用。
            """
            
            def __init__(self, client):
                self.client = client
            
            async def inject(self, prompt: str, query: str) -> str:
                """
                注入技能上下文到 Prompt。
                """
                result = await self.client.route_skills(
                    query=query,
                    context_state={},
                    max_tokens=4000
                )
                
                # 组装上下文
                context = self._assemble_context(result)
                
                # 注入到 Prompt
                return f"{context}\n\n{prompt}"
            
            def _assemble_context(self, result: dict) -> str:
                """
                组装上下文文本。
                """
                parts = ["<AvailableSkills>"]
                for skill in result["skills"]:
                    parts.append(f"Skill: {skill['id']}")
                    parts.append(f"Description: {skill['description']}")
                    parts.append(f"Instructions: {skill['instructions']}")
                    parts.append("")
                parts.append("</AvailableSkills>")
                
                return "\n".join(parts)
        
        return ContextInjector(self.client)
```

### 7.2 AutoGen 集成适配器

```python
class AutoGenAdapter:
    """
    AutoGen 框架集成适配器。
    """
    
    def __init__(self, graphskill_client):
        self.client = graphskill_client
    
    def create_skill_agent(self, name: str = "SkillRouter") -> dict:
        """
        创建 AutoGen 兼容的技能路由 Agent。
        """
        return {
            "name": name,
            "type": "assistant",
            "system_message": self._get_system_message(),
            "functions": self._get_functions()
        }
    
    def _get_system_message(self) -> str:
        """
        获取系统消息模板。
        """
        return """
        You are a Skill Router Agent. Your role is to:
        1. Analyze the user's request
        2. Retrieve relevant skills from GraphSkill
        3. Provide skill instructions to the execution agent
        
        When you receive a request, call the 'route_skills' function
        to get relevant skills, then pass the instructions to the
        appropriate agent.
        """
    
    def _get_functions(self) -> List[dict]:
        """
        获取 AutoGen Function 定义。
        """
        return [
            {
                "name": "route_skills",
                "description": "Retrieve relevant skills based on query",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The user query"
                        },
                        "max_tokens": {
                            "type": "integer",
                            "description": "Maximum token budget",
                            "default": 4000
                        }
                    },
                    "required": ["query"]
                }
            }
        ]
    
    async def handle_function_call(
        self,
        function_name: str,
        arguments: dict
    ) -> dict:
        """
        处理 AutoGen Function Call。
        """
        if function_name == "route_skills":
            result = await self.client.route_skills(
                query=arguments["query"],
                context_state={},
                max_tokens=arguments.get("max_tokens", 4000)
            )
            
            return {
                "skills": result["skills"],
                "routing_mode": result["routing_mode"],
                "token_count": result["token_count"]
            }
        
        return {"error": f"Unknown function: {function_name}"}
```

### 7.3 OpenDevin 集成适配器

```python
class OpenDevinAdapter:
    """
    OpenDevin 框架集成适配器。
    """
    
    def __init__(self, graphskill_client):
        self.client = graphskill_client
    
    def create_skill_plugin(self) -> "SkillPlugin":
        """
        创建 OpenDevin 兼容的技能插件。
        """
        class SkillPlugin:
            """
            OpenDevin 技能插件。
            """
            
            name = "graphskill"
            description = "GraphSkill dynamic skill routing"
            
            def __init__(self, client):
                self.client = client
            
            async def get_skills_for_task(
                self,
                task_description: str,
                current_state: dict
            ) -> List[dict]:
                """
                获取任务相关的技能。
                """
                result = await self.client.route_skills(
                    query=task_description,
                    context_state=current_state,
                    max_tokens=4000
                )
                
                return result["skills"]
            
            async def validate_action(
                self,
                action: dict,
                session_id: str
            ) -> bool:
                """
                校验 Action 权限。
                """
                result = await self.client.validate_permission(
                    action=action,
                    session_id=session_id
                )
                
                return result["allowed"]
        
        return SkillPlugin(self.client)
```

### 7.4 自定义框架集成指南

对于自定义 Agent 框架，集成 MUST 遵循以下步骤：

1. **调用路由 API**：通过 `/v1/route_skills` 获取技能上下文
2. **注入上下文**：将返回的技能内容注入 Agent Prompt
3. **注册 Tool Call**：将技能的 `tool_call_schema` 注册为可用工具
4. **权限校验**：在执行前调用 `/v1/validate_permission` 校验权限
5. **反馈遥测**：执行后调用 `/v1/report_execution` 报告结果

---

## 8. Tool Call JSON Schema

### 8.1 OpenAI Function Calling 格式

系统 MUST 提供兼容 OpenAI Function Calling 的 Tool Call Schema：

```python
class ToolCallSchemaGenerator:
    """
    Tool Call Schema 生成器，生成 OpenAI Function Calling 格式。
    """
    
    def generate(
        self,
        skills: List[SkillData]
    ) -> List[dict]:
        """
        生成 Tool Call Schema 列表。
        
        Args:
            skills: 技能数据列表
            
        Returns:
            List[dict]: OpenAI Function Calling 格式的 Schema
        """
        tool_definitions = []
        
        for skill in skills:
            if skill.tool_call_schema:
                tool_definitions.append({
                    "type": "function",
                    "function": {
                        "name": skill.tool_call_schema.get("name", skill.skill_id),
                        "description": skill.description,
                        "parameters": skill.tool_call_schema.get("parameters", {})
                    }
                })
            else:
                # 自动生成默认 Schema
                tool_definitions.append(self._generate_default_schema(skill))
        
        return tool_definitions
    
    def _generate_default_schema(self, skill: SkillData) -> dict:
        """
        为没有 Tool Call Schema 的技能生成默认 Schema。
        """
        return {
            "type": "function",
            "function": {
                "name": skill.skill_id.replace(":", "_"),
                "description": skill.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "The action to perform"
                        }
                    },
                    "required": ["action"]
                }
            }
        }
```

### 8.2 Tool Call Schema 示例

```json
[
  {
    "type": "function",
    "function": {
      "name": "git_commit",
      "description": "执行 Git 提交操作，将当前工作区的变更提交到本地仓库",
      "parameters": {
        "type": "object",
        "properties": {
          "message": {
            "type": "string",
            "description": "提交消息内容"
          },
          "files": {
            "type": "array",
            "items": {"type": "string"},
            "description": "要提交的文件列表，默认为全部"
          }
        },
        "required": ["message"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "git_push",
      "description": "推送本地提交到远程仓库",
      "parameters": {
        "type": "object",
        "properties": {
          "branch": {
            "type": "string",
            "description": "目标分支名称",
            "default": "main"
          },
          "remote": {
            "type": "string",
            "description": "远程仓库名称",
            "default": "origin"
          }
        },
        "required": []
      }
    }
  }
]
```

### 8.3 Tool Call 执行流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  LLM        │────▶│  Tool Call  │────▶│  Permission │────▶│  Agent      │
│  Decision   │     │  Parser     │     │  Interceptor│     │  Executor   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  [选择 Tool]         [解析参数]          [权限校验]          [执行代码]
```

---

## 9. 错误处理与异常传递

### 9.1 错误类型定义

| 错误类型 | 错误码 | 描述 | 处理策略 |
|----------|--------|------|----------|
| `PermissionDeniedError` | `PERMISSION_DENIED` | 权限校验失败 | 返回错误响应，Agent 重新规划 |
| `SkillNotInContextError` | `SKILL_NOT_IN_CONTEXT` | 技能不在当前上下文 | 返回错误响应，建议重新路由 |
| `SessionNotFoundError` | `SESSION_NOT_FOUND` | Session 不存在 | 返回错误响应，建议重新创建 |
| `RoutingError` | `ROUTING_ERROR` | 路由失败 | 返回错误响应，降级处理 |
| `TokenBudgetExceededError` | `TOKEN_BUDGET_EXCEEDED` | Token 预算超限 | 返回警告，截断上下文 |

### 9.2 错误响应格式

```python
class ErrorResponse:
    """
    标准化错误响应。
    """
    
    def __init__(
        self,
        error_type: str,
        error_code: str,
        message: str,
        details: dict,
        suggestion: str
    ):
        self.error_type = error_type
        self.error_code = error_code
        self.message = message
        self.details = details
        self.suggestion = suggestion
    
    def to_dict(self) -> dict:
        return {
            "error": {
                "type": self.error_type,
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
                "suggestion": self.suggestion
            }
        }
    
    def to_agent_format(self) -> str:
        """
        转换为 Agent 可理解的格式。
        """
        return f"""
[ERROR] {self.error_type}
Code: {self.error_code}
Message: {self.message}
Details: {json.dumps(self.details)}
Suggestion: {self.suggestion}

Please adjust your plan based on this error.
"""
```

### 9.3 异常传递机制

```python
class ExceptionHandler:
    """
    异常处理器，将内部异常转换为 Agent 可理解的响应。
    """
    
    def handle(self, exception: Exception) -> ErrorResponse:
        """
        处理异常并生成错误响应。
        """
        if isinstance(exception, PermissionDeniedError):
            return ErrorResponse(
                error_type="PermissionDenied",
                error_code="PERMISSION_DENIED",
                message=exception.reason,
                details={
                    "skill_id": exception.skill_id,
                    "action": exception.action.to_dict()
                },
                suggestion=exception._generate_suggestion()
            )
        
        elif isinstance(exception, SkillNotInContextError):
            return ErrorResponse(
                error_type="SkillNotInContext",
                error_code="SKILL_NOT_IN_CONTEXT",
                message=f"Skill '{exception.skill_id}' not in current context",
                details={"skill_id": exception.skill_id},
                suggestion="Request skill to be loaded via route_skills API"
            )
        
        elif isinstance(exception, SessionNotFoundError):
            return ErrorResponse(
                error_type="SessionNotFound",
                error_code="SESSION_NOT_FOUND",
                message=f"Session '{exception.session_id}' not found or expired",
                details={"session_id": exception.session_id},
                suggestion="Create a new session via create_session API"
            )
        
        else:
            return ErrorResponse(
                error_type="InternalError",
                error_code="INTERNAL_ERROR",
                message=str(exception),
                details={},
                suggestion="Retry the operation or contact support"
            )
```

---

## 10. 版本历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| 1.0.0 | 2026-04-12 | 初始版本发布 | GraphSkill Architecture Team |
| 1.1.0 | 2026-04-17 | VR-First 架构适配：技能注入协议优先使用 VR baseline 结果；fallback 目标从 ZS→VR baseline | GraphSkill Architecture Team |

---

**文档结束**

*本文档定义了 GraphSkill 系统的 Agent 运行时接入层。相关 API 接口规范详见 [RFC-07: API 接口规范](RFC-07-api-interface-specification.md)，安全与权限模型详见 [RFC-11: 安全与权限模型](RFC-11-security-permission-model.md)。*