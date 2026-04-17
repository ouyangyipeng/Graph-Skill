# RFC-07: API 接口规范

**文档编号:** RFC-07  
**版本:** 1.0.0  
**状态:** 正式发布  
**最后更新:** 2026-04-12  
**作者:** GraphSkill Architecture Team  
**分类:** 架构规范 - API 接口  
**依赖:** RFC-00, RFC-03, RFC-04, RFC-08

---

## 目录

1. [概述](#1-概述)
2. [API 设计原则](#2-api-设计原则)
3. [REST API 端点定义](#3-rest-api-端点定义)
4. [gRPC 服务定义](#4-grpc-服务定义)
5. [请求/响应 Schema](#5-请求响应-schema)
6. [错误码体系](#6-错误码体系)
7. [认证授权机制](#7-认证授权机制)
8. [版本控制策略](#8-版本控制策略)
9. [API 兼容性承诺](#9-api-兼容性承诺)
10. [OpenAPI 3.0 规范](#10-openapi-30-规范)
11. [版本历史](#11-版本历史)

---

## 1. 概述

### 1.1 文档目的

本文档定义 GraphSkill 系统的 API 接口规范，涵盖 REST API 端点定义、gRPC 服务定义、请求/响应 Schema、错误码体系、认证授权机制、版本控制策略、API 兼容性承诺以及 OpenAPI 3.0 规范。

### 1.2 适用范围

本文档适用于：
- 后端开发工程师：实现 API 端点
- 前端/Agent 开发者：调用 API 接口
- API 集成工程师：对接第三方系统
- 测试工程师：编写 API 测试用例

### 1.3 API 协议选择

系统 MUST 支持以下 API 协议：

| 协议 | 用途 | 适用场景 |
|------|------|----------|
| **REST (HTTP/JSON)** | 外部 API、Web 客户端 | Agent 调用、管理接口 |
| **gRPC (Protobuf)** | 内部服务间通信 | 高性能、低延迟场景 |
| **WebSocket** | 实时推送（可选） | 流式响应、实时更新 |

### 1.4 API 版本信息

| 信息 | 值 |
|------|-----|
| API 版本 | v1 |
| 基础路径 | `/v1` |
| 协议版本 | HTTP/1.1, HTTP/2 |
| 内容类型 | `application/json` |

---

## 2. API 设计原则

### 2.1 RESTful 设计规范

系统 MUST 遵循 RESTful API 设计规范：

| 原则 | 描述 | 示例 |
|------|------|------|
| **资源导向** | URL 表示资源，而非动作 | `/v1/skills/{id}` |
| **HTTP 方法语义** | 使用标准 HTTP 方法 | GET 查询, POST 创建, PUT 更新, DELETE 删除 |
| **状态码规范** | 使用标准 HTTP 状态码 | 200 成功, 400 客户端错误, 500 服务端错误 |
| **无状态** | 每个请求包含完整信息 | 不依赖 Session 状态 |
| **可缓存** | 响应包含缓存控制信息 | `Cache-Control` Header |

### 2.2 URL 设计规范

```
# URL 结构规范
https://api.graphskill.io/{version}/{resource}/{id}/{sub-resource}

# 示例
GET  /v1/skills                    # 获取技能列表
GET  /v1/skills/{skill_id}         # 获取单个技能
POST /v1/skills                    # 创建新技能
PUT  /v1/skills/{skill_id}         # 更新技能
DELETE /v1/skills/{skill_id}       # 删除技能

GET  /v1/skills/{skill_id}/edges   # 获取技能的边关系
POST /v1/skills/{skill_id}/edges   # 创建边关系

POST /v1/route                     # 执行路由（动作类 API）
POST /v1/ingest                    # 执行导入（动作类 API）
```

### 2.3 HTTP 方法使用规范

| HTTP 方法 | 用途 | 是否幂等 | 示例 |
|-----------|------|----------|------|
| **GET** | 查询资源 | 是 | `GET /v1/skills` |
| **POST** | 创建资源或执行动作 | 否 | `POST /v1/skills`, `POST /v1/route` |
| **PUT** | 更新资源（全量） | 是 | `PUT /v1/skills/{id}` |
| **PATCH** | 更新资源（部分） | 是 | `PATCH /v1/skills/{id}` |
| **DELETE** | 删除资源 | 是 | `DELETE /v1/skills/{id}` |
| **HEAD** | 获取资源元信息 | 是 | `HEAD /v1/skills/{id}` |
| **OPTIONS** | 获取支持的 HTTP 方法 | 是 | `OPTIONS /v1/skills` |

### 2.4 响应格式规范

所有 API 响应 MUST 遵循以下格式：

```json
{
  "data": { ... },           // 响应数据（成功时）
  "error": { ... },          // 错误信息（失败时）
  "meta": {                  // 元信息
    "request_id": "req_abc123",
    "timestamp": "2026-04-12T10:00:00Z",
    "version": "v1"
  }
}
```

---

## 3. REST API 端点定义

### 3.1 路由服务 API

#### 3.1.1 执行技能路由

```yaml
endpoint: /v1/route
method: POST
description: 执行技能路由，返回最小必要技能上下文

request:
  headers:
    Content-Type: application/json
    Authorization: Bearer {token}
    X-Session-ID: {session_id}
  
  body:
    type: object
    required:
      - query
    properties:
      query:
        type: string
        description: 用户查询文本
        minLength: 10
        maxLength: 2000
        example: "我需要提交当前的代码变更到 Git 仓库"
      
      context_state:
        type: object
        description: 当前 Agent 上下文状态
        properties:
          session_id:
            type: string
          previous_skills:
            type: array
            items:
              type: string
          environment:
            type: object
          agent_capabilities:
            type: array
            items:
              type: string
      
      max_tokens:
        type: integer
        description: Token 预算上限
        default: 4000
        minimum: 500
        maximum: 32000
      
      routing_options:
        type: object
        description: 路由选项配置
        properties:
          include_enhances:
            type: boolean
            default: true
          expansion_depth:
            type: integer
            default: 2
            minimum: 1
            maximum: 3
          seed_count:
            type: integer
            default: 5
            minimum: 3
            maximum: 20
          output_format:
            type: string
            enum: [xml, json, markdown]
            default: xml

response:
  headers:
    Content-Type: application/json
    X-Routing-Mode: normal|fallback|cached
    X-Routing-Latency-Ms: {latency}
    X-Request-ID: {request_id}
  
  body:
    type: object
    properties:
      data:
        type: object
        properties:
          skills:
            type: array
            items:
              type: object
              properties:
                skill_id:
                  type: string
                priority:
                  type: integer
                type:
                  type: string
                  enum: [seed, required, enhances]
                description:
                  type: string
                instructions:
                  type: string
                permissions:
                  type: array
                  items:
                    type: object
                tool_call_schema:
                  type: object
          
          routing_mode:
            type: string
            enum: [normal, fallback, cached]
          
          token_count:
            type: integer
          
          latency_ms:
            type: integer
          
          warnings:
            type: array
            items:
              type: string
      
      meta:
        type: object
        properties:
          request_id:
            type: string
          timestamp:
            type: string
          version:
            type: string

status_codes:
  - 200: 路由成功
  - 400: 请求参数错误
  - 401: 认证失败
  - 403: 权限不足
  - 429: 请求限流
  - 500: 服务内部错误
  - 503: 服务降级
```

#### 3.1.2 请求示例

```bash
# cURL 示例
curl -X POST "https://api.graphskill.io/v1/route" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "X-Session-ID: sess_abc123" \
  -d '{
    "query": "我需要提交当前的代码变更到 Git 仓库，并推送到远程分支",
    "context_state": {
      "session_id": "sess_abc123",
      "previous_skills": ["git:configure", "git:stage_files"],
      "environment": {
        "git_repo": true,
        "git_configured": true
      },
      "agent_capabilities": ["fs:read", "fs:write", "exec:git"]
    },
    "max_tokens": 4000,
    "routing_options": {
      "include_enhances": true,
      "expansion_depth": 2,
      "seed_count": 5,
      "output_format": "xml"
    }
  }'
```

#### 3.1.3 响应示例

```json
{
  "data": {
    "skills": [
      {
        "skill_id": "git:configure",
        "priority": 1,
        "type": "required",
        "description": "配置 Git 用户信息",
        "instructions": "执行 git config --global user.name \"$NAME\"",
        "permissions": [
          {"resource": "exec", "action": "run", "target": "git"}
        ],
        "tool_call_schema": {
          "name": "git_configure",
          "parameters": {
            "name": {"type": "string", "required": true},
            "email": {"type": "string", "required": true}
          }
        }
      },
      {
        "skill_id": "git:commit_changes",
        "priority": 2,
        "type": "seed",
        "description": "执行 Git 提交操作",
        "instructions": "1. git status\n2. git add -A\n3. git commit -m \"$MESSAGE\"",
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
    ],
    "routing_mode": "normal",
    "token_count": 2850,
    "latency_ms": 285,
    "warnings": []
  },
  "meta": {
    "request_id": "req_abc123def456",
    "timestamp": "2026-04-12T10:00:00Z",
    "version": "v1"
  }
}
```

### 3.2 技能管理 API

#### 3.2.1 获取技能列表

```yaml
endpoint: /v1/skills
method: GET
description: 获取技能列表

request:
  headers:
    Authorization: Bearer {token}
  
  query_params:
    page:
      type: integer
      default: 1
      description: 页码
    
    page_size:
      type: integer
      default: 20
      maximum: 100
      description: 每页数量
    
    filter:
      type: object
      properties:
        namespace:
          type: string
          description: 技能命名空间过滤
        is_deprecated:
          type: boolean
          description: 是否包含废弃技能
        tags:
          type: array
          items:
            type: string
          description: 标签过滤
    
    sort:
      type: string
      enum: [created_at, updated_at, success_rate, name]
      default: created_at
      description: 排序字段
    
    order:
      type: string
      enum: [asc, desc]
      default: desc
      description: 排序方向

response:
  body:
    type: object
    properties:
      data:
        type: object
        properties:
          skills:
            type: array
            items:
              type: object
              properties:
                skill_id:
                  type: string
                version:
                  type: string
                intent_description:
                  type: string
                is_deprecated:
                  type: boolean
                execution_success_rate:
                  type: number
                created_at:
                  type: string
                updated_at:
                  type: string
          
          pagination:
            type: object
            properties:
              page:
                type: integer
              page_size:
                type: integer
              total_count:
                type: integer
              total_pages:
                type: integer
      
      meta:
        type: object

status_codes:
  - 200: 查询成功
  - 400: 参数错误
  - 401: 认证失败
```

#### 3.2.2 获取单个技能

```yaml
endpoint: /v1/skills/{skill_id}
method: GET
description: 获取单个技能详情

request:
  path_params:
    skill_id:
      type: string
      required: true
      pattern: "^[a-z0-9_-]+:[a-z0-9_-]+$"
      description: 技能 ID

response:
  body:
    type: object
    properties:
      data:
        type: object
        properties:
          skill_id:
            type: string
          version:
            type: string
          intent_description:
            type: string
          permissions:
            type: array
          trigger_conditions:
            type: object
          topology_hints:
            type: object
          execution_success_rate:
            type: number
          execution_count:
            type: integer
          is_deprecated:
            type: boolean
          created_at:
            type: string
          updated_at:
            type: string
          edges:
            type: object
            properties:
              requires:
                type: array
              conflicts_with:
                type: array
              enhances:
                type: array
              substitutes:
                type: array

status_codes:
  - 200: 查询成功
  - 404: 技能不存在
```

#### 3.2.3 创建技能

```yaml
endpoint: /v1/skills
method: POST
description: 创建新技能

request:
  body:
    type: object
    required:
      - skill_id
      - version
      - intent_description
      - permissions
    properties:
      skill_id:
        type: string
        pattern: "^[a-z0-9_-]+:[a-z0-9_-]+$"
      version:
        type: string
        pattern: "^\\d+\\.\\d+\\.\\d+$"
      intent_description:
        type: string
        minLength: 50
        maxLength: 500
      permissions:
        type: array
        items:
          type: string
        minItems: 1
      trigger_conditions:
        type: object
      topology_hints:
        type: object
        properties:
          requires:
            type: array
          conflicts_with:
            type: array
          enhances:
            type: array
          substitutes:
            type: array
      content:
        type: string
        description: 技能内容（Markdown 格式）

response:
  body:
    type: object
    properties:
      data:
        type: object
        properties:
          skill_id:
            type: string
          status:
            type: string
            enum: [pending, active, rejected]
          validation_result:
            type: object
          created_at:
            type: string

status_codes:
  - 201: 创建成功
  - 400: 参数错误
  - 409: 技能 ID 已存在
```

#### 3.2.4 更新技能

```yaml
endpoint: /v1/skills/{skill_id}
method: PUT
description: 更新技能（全量更新）

request:
  path_params:
    skill_id:
      type: string
      required: true
  
  body:
    type: object
    required:
      - version
      - intent_description
      - permissions
    properties:
      version:
        type: string
      intent_description:
        type: string
      permissions:
        type: array
      trigger_conditions:
        type: object
      topology_hints:
        type: object
      content:
        type: string

response:
  body:
    type: object
    properties:
      data:
        type: object
        properties:
          skill_id:
            type: string
          updated_at:
            type: string

status_codes:
  - 200: 更新成功
  - 400: 参数错误
  - 404: 技能不存在
```

#### 3.2.5 删除技能（软删除）

```yaml
endpoint: /v1/skills/{skill_id}
method: DELETE
description: 删除技能（软删除，标记为 deprecated）

request:
  path_params:
    skill_id:
      type: string
      required: true
  
  query_params:
    reason:
      type: string
      description: 删除原因

response:
  body:
    type: object
    properties:
      data:
        type: object
        properties:
          skill_id:
            type: string
          is_deprecated:
            type: boolean
          deprecated_at:
            type: string
          deprecation_reason:
            type: string

status_codes:
  - 200: 删除成功
  - 404: 技能不存在
```

### 3.3 边关系管理 API

#### 3.3.1 获取技能边关系

```yaml
endpoint: /v1/skills/{skill_id}/edges
method: GET
description: 获取技能的所有边关系

request:
  path_params:
    skill_id:
      type: string
      required: true
  
  query_params:
    edge_type:
      type: string
      enum: [REQUIRES, CONFLICTS_WITH, ENHANCES, SUBSTITUTES, all]
      default: all
      description: 边类型过滤

response:
  body:
    type: object
    properties:
      data:
        type: object
        properties:
          skill_id:
            type: string
          edges:
            type: array
            items:
              type: object
              properties:
                source:
                  type: string
                target:
                  type: string
                edge_type:
                  type: string
                properties:
                  type: object
                  properties:
                    weight:
                      type: number
                    is_hard:
                      type: boolean
                    severity:
                      type: integer
                    verified_by_human:
                      type: boolean
                    auto_discovered:
                      type: boolean
                    created_at:
                      type: string
```

#### 3.3.2 创建边关系

```yaml
endpoint: /v1/skills/{skill_id}/edges
method: POST
description: 创建技能边关系

request:
  path_params:
    skill_id:
      type: string
      required: true
  
  body:
    type: object
    required:
      - target_skill_id
      - edge_type
    properties:
      target_skill_id:
        type: string
      edge_type:
        type: string
        enum: [REQUIRES, CONFLICTS_WITH, ENHANCES, SUBSTITUTES]
      properties:
        type: object
        properties:
          weight:
            type: number
            default: 1.0
          is_hard:
            type: boolean
            default: true
          severity:
            type: integer
            default: 3
          reason:
            type: string

response:
  status_codes:
    - 201: 创建成功
    - 400: 参数错误
    - 404: 技能不存在
    - 409: 边已存在
    - 422: DAG 环路检测失败
```

### 3.4 导入服务 API

#### 3.4.1 执行技能导入

```yaml
endpoint: /v1/ingest
method: POST
description: 执行技能文件导入

request:
  body:
    type: object
    required:
      - source
    properties:
      source:
        type: object
        properties:
          type:
            type: string
            enum: [file, git_repo, url]
          path:
            type: string
            description: 文件路径或 Git 仓库 URL
          branch:
            type: string
            description: Git 分支（可选）
      
      options:
        type: object
        properties:
          validation_mode:
            type: string
            enum: [strict, lenient]
            default: strict
          auto_infer_topology:
            type: boolean
            default: true
          skip_dag_check:
            type: boolean
            default: false

response:
  body:
    type: object
    properties:
      data:
        type: object
        properties:
          import_id:
            type: string
          status:
            type: string
            enum: [pending, processing, completed, failed]
          total_files:
            type: integer
          successful:
            type: integer
          failed:
            type: integer
          errors:
            type: array
            items:
              type: object
              properties:
                file_path:
                  type: string
                error_type:
                  type: string
                error_message:
                  type: string

status_codes:
  - 202: 导入任务已接受（异步处理）
  - 400: 参数错误
```

#### 3.4.2 执行批量导入

```yaml
endpoint: /v1/ingest/batch
method: POST
description: 执行批量技能导入

request:
  body:
    type: object
    required:
      - files
    properties:
      files:
        type: array
        items:
          type: string
        description: 文件路径列表
        minItems: 1
        maxItems: 100
      
      options:
        type: object
        properties:
          validation_mode:
            type: string
            default: strict
          parallel_workers:
            type: integer
            default: 4
            maximum: 10

response:
  body:
    type: object
    properties:
      data:
        type: object
        properties:
          batch_id:
            type: string
          status:
            type: string
          total_files:
            type: integer
          successful:
            type: integer
          failed:
            type: integer
          skipped:
            type: integer
          duration_seconds:
            type: number
          errors:
            type: array

status_codes:
  - 202: 批量导入任务已接受
```

### 3.5 权限校验 API

#### 3.5.1 校验技能调用权限

```yaml
endpoint: /v1/validate_permission
method: POST
description: 校验技能调用权限

request:
  body:
    type: object
    required:
      - skill_id
      - action
      - session_id
    properties:
      skill_id:
        type: string
      action:
        type: object
        properties:
          tool_name:
            type: string
          parameters:
            type: object
      session_id:
        type: string

response:
  body:
    type: object
    properties:
      data:
        type: object
        properties:
          allowed:
            type: boolean
          reason:
            type: string
          error_code:
            type: string
          skill_permissions:
            type: array
          session_authorization:
            type: object

status_codes:
  - 200: 校验完成
  - 400: 参数错误
  - 404: Session 不存在
```

### 3.6 遥测反馈 API

#### 3.6.1 报告技能执行结果

```yaml
endpoint: /v1/report_execution
method: POST
description: 报告技能执行结果（供 Agent 调用）

request:
  body:
    type: object
    required:
      - skill_id
      - session_id
      - status
    properties:
      skill_id:
        type: string
      session_id:
        type: string
      status:
        type: string
        enum: [SUCCESS, FAILED, TIMEOUT]
      duration_ms:
        type: number
      error_type:
        type: string
      error_message:
        type: string
      result_summary:
        type: string

response:
  body:
    type: object
    properties:
      data:
        type: object
        properties:
          recorded:
            type: boolean
          updated_reliability:
            type: number

status_codes:
  - 200: 报告成功
  - 400: 参数错误
```

### 3.7 Session 管理 API

#### 3.7.1 创建 Session

```yaml
endpoint: /v1/sessions
method: POST
description: 创建 Agent Session

request:
  body:
    type: object
    required:
      - agent_id
    properties:
      agent_id:
        type: string
      authorization:
        type: object
        properties:
          permissions:
            type: array
          skills:
            type: array
          expires_in_seconds:
            type: integer
            default: 86400

response:
  body:
    type: object
    properties:
      data:
        type: object
        properties:
          session_id:
            type: string
          agent_id:
            type: string
          created_at:
            type: string
          expires_at:
            type: string
          authorization:
            type: object

status_codes:
  - 201: 创建成功
```

#### 3.7.2 获取 Session

```yaml
endpoint: /v1/sessions/{session_id}
method: GET
description: 获取 Session 详情

request:
  path_params:
    session_id:
      type: string
      required: true

response:
  body:
    type: object
    properties:
      data:
        type: object
        properties:
          session_id:
            type: string
          agent_id:
            type: string
          current_context:
            type: object
          execution_state:
            type: object
          created_at:
            type: string
          expires_at:
            type: string

status_codes:
  - 200: 查询成功
  - 404: Session 不存在
```

#### 3.7.3 终止 Session

```yaml
endpoint: /v1/sessions/{session_id}
method: DELETE
description: 终止 Session

request:
  path_params:
    session_id:
      type: string
      required: true

response:
  status_codes:
    - 200: 终止成功
    - 404: Session 不存在
```

### 3.8 健康检查 API

#### 3.8.1 服务健康检查

```yaml
endpoint: /v1/health
method: GET
description: 服务健康检查

response:
  body:
    type: object
    properties:
      data:
        type: object
        properties:
          status:
            type: string
            enum: [healthy, degraded, unhealthy]
          components:
            type: object
            properties:
              graph_db:
                type: object
                properties:
                  status:
                    type: string
                  latency_ms:
                    type: number
              vector_db:
                type: object
                properties:
                  status:
                    type: string
                  latency_ms:
                    type: number
              redis:
                type: object
                properties:
                  status:
                    type: string
              kafka:
                type: object
                properties:
                  status:
                    type: string
          version:
            type: string
          uptime_seconds:
            type: integer

status_codes:
  - 200: 服务健康
  - 503: 服务不健康
```

---

## 4. gRPC 服务定义

### 4.1 Proto 文件定义

```protobuf
// graphskill.proto

syntax = "proto3";

package graphskill.v1;

option go_package = "github.com/graphskill/api/v1;v1";
option java_package = "io.graphskill.api.v1";

// 路由服务
service RoutingService {
  // 执行技能路由
  rpc Route(RouteRequest) returns (RouteResponse);
  
  // 流式路由（实时更新）
  rpc RouteStream(stream RouteRequest) returns (stream RouteResponse);
}

// 技能管理服务
service SkillService {
  // 获取技能列表
  rpc ListSkills(ListSkillsRequest) returns (ListSkillsResponse);
  
  // 获取单个技能
  rpc GetSkill(GetSkillRequest) returns (GetSkillResponse);
  
  // 创建技能
  rpc CreateSkill(CreateSkillRequest) returns (CreateSkillResponse);
  
  // 更新技能
  rpc UpdateSkill(UpdateSkillRequest) returns (UpdateSkillResponse);
  
  // 删除技能
  rpc DeleteSkill(DeleteSkillRequest) returns (DeleteSkillResponse);
}

// 边关系管理服务
service EdgeService {
  // 获取边关系
  rpc GetEdges(GetEdgesRequest) returns (GetEdgesResponse);
  
  // 创建边关系
  rpc CreateEdge(CreateEdgeRequest) returns (CreateEdgeResponse);
  
  // 删除边关系
  rpc DeleteEdge(DeleteEdgeRequest) returns (DeleteEdgeResponse);
}

// 导入服务
service IngestionService {
  // 执行导入
  rpc Ingest(IngestRequest) returns (IngestResponse);
  
  // 批量导入
  rpc BatchIngest(BatchIngestRequest) returns (BatchIngestResponse);
}

// 权限校验服务
service PermissionService {
  // 校验权限
  rpc ValidatePermission(ValidatePermissionRequest) returns (ValidatePermissionResponse);
}

// 遥测服务
service TelemetryService {
  // 报告执行结果
  rpc ReportExecution(ReportExecutionRequest) returns (ReportExecutionResponse);
}

// Session 服务
service SessionService {
  // 创建 Session
  rpc CreateSession(CreateSessionRequest) returns (CreateSessionResponse);
  
  // 获取 Session
  rpc GetSession(GetSessionRequest) returns (GetSessionResponse);
  
  // 终止 Session
  rpc TerminateSession(TerminateSessionRequest) returns (TerminateSessionResponse);
}

// ============ 消息定义 ============

// 路由请求
message RouteRequest {
  string query = 1;
  ContextState context_state = 2;
  int32 max_tokens = 3;
  RoutingOptions routing_options = 4;
}

message ContextState {
  string session_id = 1;
  repeated string previous_skills = 2;
  map<string, string> environment = 3;
  repeated string agent_capabilities = 4;
}

message RoutingOptions {
  bool include_enhances = 1;
  int32 expansion_depth = 2;
  int32 seed_count = 3;
  string output_format = 4;
}

// 路由响应
message RouteResponse {
  repeated SkillData skills = 1;
  string routing_mode = 2;
  int32 token_count = 3;
  int32 latency_ms = 4;
  repeated string warnings = 5;
  ResponseMeta meta = 6;
}

message SkillData {
  string skill_id = 1;
  int32 priority = 2;
  string type = 3;
  string description = 4;
  string instructions = 5;
  repeated Permission permissions = 6;
  ToolCallSchema tool_call_schema = 7;
}

message Permission {
  string resource = 1;
  string action = 2;
  string target = 3;
}

message ToolCallSchema {
  string name = 1;
  string parameters_json = 2;  // JSON 格式的参数定义
}

message ResponseMeta {
  string request_id = 1;
  string timestamp = 2;
  string version = 3;
}

// 技能列表请求
message ListSkillsRequest {
  int32 page = 1;
  int32 page_size = 2;
  SkillFilter filter = 3;
  string sort = 4;
  string order = 5;
}

message SkillFilter {
  string namespace = 1;
  bool include_deprecated = 2;
  repeated string tags = 3;
}

// 技能列表响应
message ListSkillsResponse {
  repeated SkillSummary skills = 1;
  Pagination pagination = 2;
  ResponseMeta meta = 3;
}

message SkillSummary {
  string skill_id = 1;
  string version = 2;
  string intent_description = 3;
  bool is_deprecated = 4;
  float execution_success_rate = 5;
  string created_at = 6;
  string updated_at = 7;
}

message Pagination {
  int32 page = 1;
  int32 page_size = 2;
  int32 total_count = 3;
  int32 total_pages = 4;
}

// 获取技能请求
message GetSkillRequest {
  string skill_id = 1;
}

// 获取技能响应
message GetSkillResponse {
  SkillDetail skill = 1;
  ResponseMeta meta = 2;
}

message SkillDetail {
  string skill_id = 1;
  string version = 2;
  string intent_description = 3;
  repeated Permission permissions = 4;
  map<string, string> trigger_conditions = 5;
  TopologyHints topology_hints = 6;
  float execution_success_rate = 7;
  int32 execution_count = 8;
  bool is_deprecated = 9;
  string created_at = 10;
  string updated_at = 11;
  SkillEdges edges = 12;
}

message TopologyHints {
  repeated string requires = 1;
  repeated string conflicts_with = 2;
  repeated string enhances = 3;
  repeated string substitutes = 4;
}

message SkillEdges {
  repeated Edge requires = 1;
  repeated Edge conflicts_with = 2;
  repeated Edge enhances = 3;
  repeated Edge substitutes = 4;
}

message Edge {
  string source = 1;
  string target = 2;
  string edge_type = 3;
  EdgeProperties properties = 4;
}

message EdgeProperties {
  float weight = 1;
  bool is_hard = 2;
  int32 severity = 3;
  bool verified_by_human = 4;
  bool auto_discovered = 5;
  string created_at = 6;
}

// 创建技能请求
message CreateSkillRequest {
  string skill_id = 1;
  string version = 2;
  string intent_description = 3;
  repeated Permission permissions = 4;
  map<string, string> trigger_conditions = 5;
  TopologyHints topology_hints = 6;
  string content = 7;
}

// 创建技能响应
message CreateSkillResponse {
  string skill_id = 1;
  string status = 2;
  ValidationResult validation_result = 3;
  string created_at = 4;
  ResponseMeta meta = 5;
}

message ValidationResult {
  bool valid = 1;
  repeated ValidationError errors = 2;
}

message ValidationError {
  string field = 1;
  string message = 2;
  string error_code = 3;
}

// 更新技能请求
message UpdateSkillRequest {
  string skill_id = 1;
  string version = 2;
  string intent_description = 3;
  repeated Permission permissions = 4;
  map<string, string> trigger_conditions = 5;
  TopologyHints topology_hints = 6;
  string content = 7;
}

// 更新技能响应
message UpdateSkillResponse {
  string skill_id = 1;
  string updated_at = 2;
  ResponseMeta meta = 3;
}

// 删除技能请求
message DeleteSkillRequest {
  string skill_id = 1;
  string reason = 2;
}

// 删除技能响应
message DeleteSkillResponse {
  string skill_id = 1;
  bool is_deprecated = 2;
  string deprecated_at = 3;
  string deprecation_reason = 4;
  ResponseMeta meta = 5;
}

// 导入请求
message IngestRequest {
  IngestSource source = 1;
  IngestOptions options = 2;
}

message IngestSource {
  string type = 1;  // file, git_repo, url
  string path = 2;
  string branch = 3;
}

message IngestOptions {
  string validation_mode = 1;
  bool auto_infer_topology = 2;
  bool skip_dag_check = 3;
}

// 导入响应
message IngestResponse {
  string import_id = 1;
  string status = 2;
  int32 total_files = 3;
  int32 successful = 4;
  int32 failed = 5;
  repeated IngestError errors = 6;
  ResponseMeta meta = 7;
}

message IngestError {
  string file_path = 1;
  string error_type = 2;
  string error_message = 3;
}

// 批量导入请求
message BatchIngestRequest {
  repeated string files = 1;
  IngestOptions options = 2;
}

// 批量导入响应
message BatchIngestResponse {
  string batch_id = 1;
  string status = 2;
  int32 total_files = 3;
  int32 successful = 4;
  int32 failed = 5;
  int32 skipped = 6;
  float duration_seconds = 7;
  repeated IngestError errors = 8;
  ResponseMeta meta = 9;
}

// 权限校验请求
message ValidatePermissionRequest {
  string skill_id = 1;
  Action action = 2;
  string session_id = 3;
}

message Action {
  string tool_name = 1;
  map<string, string> parameters = 2;
}

// 权限校验响应
message ValidatePermissionResponse {
  bool allowed = 1;
  string reason = 2;
  string error_code = 3;
  repeated Permission skill_permissions = 4;
  SessionAuthorization session_authorization = 5;
  ResponseMeta meta = 6;
}

message SessionAuthorization {
  string session_id = 1;
  repeated Permission permissions = 2;
  repeated string skills = 3;
  string expires_at = 4;
}

// 报告执行请求
message ReportExecutionRequest {
  string skill_id = 1;
  string session_id = 2;
  string status = 3;  // SUCCESS, FAILED, TIMEOUT
  float duration_ms = 4;
  string error_type = 5;
  string error_message = 6;
  string result_summary = 7;
}

// 报告执行响应
message ReportExecutionResponse {
  bool recorded = 1;
  float updated_reliability = 2;
  ResponseMeta meta = 3;
}

// 创建 Session 请求
message CreateSessionRequest {
  string agent_id = 1;
  SessionAuthorization authorization = 2;
}

// 创建 Session 响应
message CreateSessionResponse {
  string session_id = 1;
  string agent_id = 2;
  string created_at = 3;
  string expires_at = 4;
  SessionAuthorization authorization = 5;
  ResponseMeta meta = 6;
}

// 获取 Session 请求
message GetSessionRequest {
  string session_id = 1;
}

// 获取 Session 响应
message GetSessionResponse {
  string session_id = 1;
  string agent_id = 2;
  SessionContext current_context = 3;
  ExecutionState execution_state = 4;
  string created_at = 5;
  string expires_at = 6;
  ResponseMeta meta = 7;
}

message SessionContext {
  repeated string skills = 1;
  string routing_mode = 2;
  string last_routing_time = 3;
  int32 token_count = 4;
}

message ExecutionState {
  string status = 1;
  string current_skill = 2;
  repeated Action pending_actions = 3;
}

// 终止 Session 请求
message TerminateSessionRequest {
  string session_id = 1;
}

// 终止 Session 响应
message TerminateSessionResponse {
  bool terminated = 1;
  ResponseMeta meta = 2;
}
```

### 4.2 gRPC 客户端示例

```python
# Python gRPC 客户端示例

import grpc
from graphskill.v1 import routing_pb2, routing_pb2_grpc

class GraphSkillClient:
    """
    GraphSkill gRPC 客户端。
    """
    
    def __init__(self, host: str, port: int):
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.routing_stub = routing_pb2_grpc.RoutingServiceStub(self.channel)
        self.skill_stub = routing_pb2_grpc.SkillServiceStub(self.channel)
    
    async def route(
        self,
        query: str,
        context_state: dict,
        max_tokens: int = 4000
    ) -> RouteResponse:
        """
        执行技能路由。
        """
        request = routing_pb2.RouteRequest(
            query=query,
            context_state=routing_pb2.ContextState(
                session_id=context_state.get("session_id", ""),
                previous_skills=context_state.get("previous_skills", []),
                environment=context_state.get("environment", {}),
                agent_capabilities=context_state.get("agent_capabilities", [])
            ),
            max_tokens=max_tokens
        )
        
        response = await self.routing_stub.Route(request)
        
        return response
```

---

## 5. 请求/响应 Schema

### 5.1 通用响应 Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://api.graphskill.io/schemas/response-v1.json",
  "title": "GraphSkill API Response Schema",
  "type": "object",
  "required": ["meta"],
  "properties": {
    "data": {
      "type": "object",
      "description": "响应数据（成功时存在）"
    },
    "error": {
      "type": "object",
      "description": "错误信息（失败时存在）",
      "properties": {
        "type": {"type": "string"},
        "code": {"type": "string"},
        "message": {"type": "string"},
        "details": {"type": "object"},
        "suggestion": {"type": "string"}
      }
    },
    "meta": {
      "type": "object",
      "required": ["request_id", "timestamp", "version"],
      "properties": {
        "request_id": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"},
        "version": {"type": "string"},
        "latency_ms": {"type": "integer"}
      }
    }
  }
}
```

### 5.2 路由请求 Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://api.graphskill.io/schemas/route-request-v1.json",
  "title": "Route Request Schema",
  "type": "object",
  "required": ["query"],
  "properties": {
    "query": {
      "type": "string",
      "minLength": 10,
      "maxLength": 2000,
      "description": "用户查询文本"
    },
    "context_state": {
      "type": "object",
      "properties": {
        "session_id": {"type": "string"},
        "previous_skills": {
          "type": "array",
          "items": {"type": "string"}
        },
        "environment": {
          "type": "object",
          "additionalProperties": {"type": "string"}
        },
        "agent_capabilities": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    },
    "max_tokens": {
      "type": "integer",
      "default": 4000,
      "minimum": 500,
      "maximum": 32000
    },
    "routing_options": {
      "type": "object",
      "properties": {
        "include_enhances": {"type": "boolean", "default": true},
        "expansion_depth": {"type": "integer", "default": 2, "minimum": 1, "maximum": 3},
        "seed_count": {"type": "integer", "default": 5, "minimum": 3, "maximum": 20},
        "output_format": {"type": "string", "enum": ["xml", "json", "markdown"], "default": "xml"}
      }
    }
  }
}
```

---

## 6. 错误码体系

### 6.1 错误码分类

| 类别 | 错误码范围 | 描述 |
|------|------------|------|
| **客户端错误** | 1000-1999 | 请求参数、认证、权限等问题 |
| **服务端错误** | 2000-2999 | 服务内部错误 |
| **业务错误** | 3000-3999 | 业务逻辑错误 |
| **外部依赖错误** | 4000-4999 | 外部服务错误 |

### 6.2 错误码定义

| 错误码 | 名称 | HTTP 状态码 | 描述 |
|--------|------|-------------|------|
| **1001** | `INVALID_REQUEST` | 400 | 请求参数格式错误 |
| **1002** | `MISSING_REQUIRED_FIELD` | 400 | 缺少必填字段 |
| **1003** | `INVALID_SKILL_ID_FORMAT` | 400 | 技能 ID 格式不合规 |
| **1004** | `INVALID_VERSION_FORMAT` | 400 | 版本号格式不合规 |
| **1005** | `INVALID_PERMISSION_FORMAT` | 400 | 权限声明格式不合规 |
| **1010** | `AUTHENTICATION_FAILED` | 401 | 认证失败 |
| **1011** | `TOKEN_EXPIRED` | 401 | Token 已过期 |
| **1012** | `INVALID_TOKEN` | 401 | Token 无效 |
| **1020** | `PERMISSION_DENIED` | 403 | 权限不足 |
| **1021** | `SKILL_NOT_IN_CONTEXT` | 403 | 技能不在当前上下文 |
| **1022** | `SESSION_NOT_AUTHORIZED` | 403 | Session 未授权 |
| **1030** | `RATE_LIMIT_EXCEEDED` | 429 | 请求限流 |
| **1040** | `RESOURCE_NOT_FOUND` | 404 | 资源不存在 |
| **1041** | `SKILL_NOT_FOUND` | 404 | 技能不存在 |
| **1042** | `SESSION_NOT_FOUND` | 404 | Session 不存在 |
| **1050** | `RESOURCE_ALREADY_EXISTS` | 409 | 资源已存在 |
| **1051** | `SKILL_ID_EXISTS` | 409 | 技能 ID 已存在 |
| **1052** | `EDGE_EXISTS` | 409 | 边关系已存在 |
| **2001** | `INTERNAL_ERROR` | 500 | 服务内部错误 |
| **2002** | `ROUTING_ERROR` | 500 | 路由处理错误 |
| **2003** | `DATABASE_ERROR` | 500 | 数据库错误 |
| **2010** | `SERVICE_UNAVAILABLE` | 503 | 服务不可用 |
| **2011** | `SERVICE_DEGRADED` | 503 | 服务降级 |
| **3001** | `TOPOLOGY_CYCLE_ERROR` | 422 | 拓扑环路检测失败 |
| **3002** | `SCHEMA_VALIDATION_ERROR` | 400 | Schema 校验失败 |
| **3003** | `DAG_VALIDATION_ERROR` | 422 | DAG 校验失败 |
| **3004** | `CONFLICT_PRUNING_ERROR` | 500 | 冲突剪枝错误 |
| **3005** | `TOKEN_BUDGET_EXCEEDED` | 400 | Token 预算超限 |
| **4001** | `GRAPH_DB_ERROR` | 503 | 图数据库错误 |
| **4002** | `VECTOR_DB_ERROR` | 503 | 向量数据库错误 |
| **4003** | `REDIS_ERROR` | 503 | Redis 错误 |
| **4004** | `KAFKA_ERROR` | 503 | Kafka 错误 |
| **4005** | `LLM_API_ERROR` | 503 | LLM API 错误 |

### 6.3 错误响应格式

```json
{
  "error": {
    "type": "ValidationError",
    "code": "1003",
    "message": "Skill ID format is invalid",
    "details": {
      "field": "skill_id",
      "value": "invalid-format",
      "expected": "^[a-z0-9_-]+:[a-z0-9_-]+$"
    },
    "suggestion": "Use format: namespace:action (e.g., git:commit)"
  },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2026-04-12T10:00:00Z",
    "version": "v1"
  }
}
```

---

## 7. 认证授权机制

### 7.1 认证方式

系统 MUST 支持以下认证方式：

| 认证方式 | 适用场景 | Header 格式 |
|----------|----------|-------------|
| **Bearer Token (JWT)** | API 调用 | `Authorization: Bearer {token}` |
| **API Key** | 服务间调用 | `X-API-Key: {key}` |
| **Session Token** | Agent Session | `X-Session-ID: {session_id}` |

### 7.2 JWT Token 结构

```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "key-001"
  },
  "payload": {
    "iss": "graphskill.io",
    "sub": "agent_001",
    "aud": "api.graphskill.io",
    "exp": 1712345678,
    "iat": 1712345678,
    "jti": "token_abc123",
    "permissions": ["fs:read", "exec:git"],
    "session_id": "sess_abc123"
  },
  "signature": "..."
}
```

### 7.3 认证流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Client     │────▶│  API        │────▶│  Auth       │────▶│  Request    │
│  Request    │     │  Gateway    │     │  Validator  │     │  Handler    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  [携带 Token]        [提取 Token]        [验证 Token]        [处理请求]
```

### 7.4 认证中间件实现

```python
class AuthenticationMiddleware:
    """
    认证中间件。
    """
    
    async def authenticate(self, request: Request) -> AuthResult:
        """
        执行认证。
        """
        # 提取 Token
        token = self._extract_token(request)
        
        if not token:
            return AuthResult(
                success=False,
                error_code="1010",
                error_message="Authentication token missing"
            )
        
        # 验证 Token
        try:
            payload = await self._verify_token(token)
            
            return AuthResult(
                success=True,
                agent_id=payload.get("sub"),
                session_id=payload.get("session_id"),
                permissions=payload.get("permissions", [])
            )
            
        except TokenExpiredError:
            return AuthResult(
                success=False,
                error_code="1011",
                error_message="Token expired"
            )
        
        except InvalidTokenError:
            return AuthResult(
                success=False,
                error_code="1012",
                error_message="Invalid token"
            )
    
    def _extract_token(self, request: Request) -> str:
        """
        从请求中提取 Token。
        """
        # Bearer Token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        
        # API Key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key
        
        return None
    
    async def _verify_token(self, token: str) -> dict:
        """
        验证 Token。
        """
        # JWT 验证
        import jwt
        
        public_key = await self._get_public_key()
        
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience="api.graphskill.io"
        )
        
        return payload
```

---

## 8. 版本控制策略

### 8.1 API 版本策略

系统 MUST 采用 URL 路径版本控制：

```
# 版本格式
https://api.graphskill.io/{version}/{resource}

# 当前版本
https://api.graphskill.io/v1/skills

# 未来版本
https://api.graphskill.io/v2/skills
```

### 8.2 版本生命周期

| 阶段 | 描述 | 持续时间 |
|------|------|----------|
| **Current** | 当前活跃版本，完整支持 | - |
| **Deprecated** | 已废弃，仅维护安全修复 | 6 个月 |
| **Retired** | 已退役，不再支持 | - |

### 8.3 版本废弃通知

当 API 版本进入废弃阶段时，系统 MUST 在响应 Header 中添加废弃通知：

```
# 响应 Header
X-API-Version: v1
X-API-Deprecated: true
X-API-Sunset: 2026-10-12T00:00:00Z
Link: </v2/skills>; rel="successor-version"
```

---

## 9. API 兼容性承诺

### 9.1 兼容性保证

系统 MUST 保证以下兼容性：

| 保证类型 | 描述 | 示例 |
|----------|------|------|
| **向后兼容** | 新版本 MUST 不破坏现有客户端 | 不删除已有字段 |
| **添加兼容** | 新字段 MAY 添加，不影响现有客户端 | 添加可选字段 |
| **类型兼容** | 字段类型 MUST NOT 变更 | 不改变 string 为 integer |

### 9.2 破坏性变更定义

以下变更被视为破坏性变更，MUST NOT 在同一版本内执行：

| 变更类型 | 描述 |
|----------|------|
| 删除端点 | 移除已有 API 端点 |
| 删除字段 | 移除响应中的已有字段 |
| 变更字段名 | 重命名已有字段 |
| 变更字段类型 | 改变字段数据类型 |
| 变更必填性 | 将可选字段变为必填 |
| 变更默认值 | 改变字段默认值 |

### 9.3 兼容性变更流程

当需要执行破坏性变更时，MUST 遵循以下流程：

1. 发布新版本 API（v2）
2. 标记旧版本为 Deprecated
3. 提供迁移指南
4. 6 个月后退役旧版本

---

## 10. OpenAPI 3.0 规范

### 10.1 OpenAPI 文档结构

```yaml
openapi: 3.0.3
info:
  title: GraphSkill API
  description: |
    GraphSkill 是拓扑感知的 Agent 过程性知识动态路由框架。
    
    ## 核心功能
    - 技能路由：根据 Query 动态返回最小必要技能上下文
    - 技能管理：创建、更新、删除技能
    - 边关系管理：管理技能间的拓扑关系
    - 权限校验：校验技能调用权限
    
  version: 1.0.0
  contact:
    name: GraphSkill Team
    email: api@graphskill.io
    url: https://graphskill.io
  
servers:
  - url: https://api.graphskill.io/v1
    description: Production Server
  - url: https://api-staging.graphskill.io/v1
    description: Staging Server

tags:
  - name: Routing
    description: 技能路由相关 API
  - name: Skills
    description: 技能管理相关 API
  - name: Edges
    description: 边关系管理相关 API
  - name: Ingestion
    description: 技能导入相关 API
  - name: Permissions
    description: 权限校验相关 API
  - name: Sessions
    description: Session 管理相关 API
  - name: Telemetry
    description: 遥测反馈相关 API

paths:
  /route:
    post:
      tags:
        - Routing
      summary: 执行技能路由
      description: 根据用户 Query 动态返回最小必要技能上下文
      operationId: routeSkills
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RouteRequest'
            examples:
              basic:
                summary: 基本路由请求
                value:
                  query: "我需要提交代码变更"
                  max_tokens: 4000
              with_context:
                summary: 带上下文的路由请求
                value:
                  query: "我需要提交代码变更并推送"
                  context_state:
                    session_id: "sess_abc123"
                    previous_skills: ["git:configure"]
                  max_tokens: 4000
      
      responses:
        '200':
          description: 路由成功
          headers:
            X-Routing-Mode:
              description: 路由模式
              schema:
                type: string
                enum: [normal, fallback, cached]
            X-Routing-Latency-Ms:
              description: 路由延迟（毫秒）
              schema:
                type: integer
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RouteResponse'
        
        '400':
          description: 请求参数错误
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        
        '401':
          description: 认证失败
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        
        '429':
          description: 请求限流
          headers:
            Retry-After:
              description: 重试等待时间（秒）
              schema:
                type: integer
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        
        '503':
          description: 服务降级
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /skills:
    get:
      tags:
        - Skills
      summary: 获取技能列表
      operationId: listSkills
      security:
        - bearerAuth: []
      parameters:
        - name: page
          in: query
          schema:
            type: integer
            default: 1
        - name: page_size
          in: query
          schema:
            type: integer
            default: 20
            maximum: 100
        - name: namespace
          in: query
          schema:
            type: string
        - name: include_deprecated
          in: query
          schema:
            type: boolean
            default: false
      
      responses:
        '200':
          description: 查询成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ListSkillsResponse'
    
    post:
      tags:
        - Skills
      summary: 创建新技能
      operationId: createSkill
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateSkillRequest'
      
      responses:
        '201':
          description: 创建成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CreateSkillResponse'
        
        '400':
          description: 参数错误
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        
        '409':
          description: 技能 ID 已存在
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /skills/{skill_id}:
    get:
      tags:
        - Skills
      summary: 获取单个技能
      operationId: getSkill
      security:
        - bearerAuth: []
      parameters:
        - name: skill_id
          in: path
          required: true
          schema:
            type: string
            pattern: '^[a-z0-9_-]+:[a-z0-9_-]+$'
      
      responses:
        '200':
          description: 查询成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/GetSkillResponse'
        
        '404':
          description: 技能不存在
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
    
    put:
      tags:
        - Skills
      summary: 更新技能
      operationId: updateSkill
      security:
        - bearerAuth: []
      parameters:
        - name: skill_id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UpdateSkillRequest'
      
      responses:
        '200':
          description: 更新成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UpdateSkillResponse'
    
    delete:
      tags:
        - Skills
      summary: 删除技能（软删除）
      operationId: deleteSkill
      security:
        - bearerAuth: []
      parameters:
        - name: skill_id
          in: path
          required: true
          schema:
            type: string
        - name: reason
          in: query
          schema:
            type: string
      
      responses:
        '200':
          description: 删除成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DeleteSkillResponse'

  /health:
    get:
      tags:
        - Health
      summary: 服务健康检查
      operationId: healthCheck
      responses:
        '200':
          description: 服务健康
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HealthResponse'
        
        '503':
          description: 服务不健康
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HealthResponse'

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: JWT Token 认证
    
    apiKey:
      type: apiKey
      in: header
      name: X-API-Key
      description: API Key 认证
  
  schemas:
    RouteRequest:
      type: object
      required:
        - query
      properties:
        query:
          type: string
          minLength: 10
          maxLength: 2000
        context_state:
          type: object
          properties:
            session_id:
              type: string
            previous_skills:
              type: array
              items:
                type: string
            environment:
              type: object
              additionalProperties:
                type: string
        max_tokens:
          type: integer
          default: 4000
          minimum: 500
          maximum: 32000
        routing_options:
          type: object
          properties:
            include_enhances:
              type: boolean
              default: true
            expansion_depth:
              type: integer
              default: 2
            seed_count:
              type: integer
              default: 5
            output_format:
              type: string
              enum: [xml, json, markdown]
              default: xml
    
    RouteResponse:
      type: object
      required:
        - data
        - meta
      properties:
        data:
          type: object
          properties:
            skills:
              type: array
              items:
                $ref: '#/components/schemas/SkillData'
            routing_mode:
              type: string
              enum: [normal, fallback, cached]
            token_count:
              type: integer
            latency_ms:
              type: integer
            warnings:
              type: array
              items:
                type: string
        meta:
          $ref: '#/components/schemas/ResponseMeta'
    
    SkillData:
      type: object
      properties:
        skill_id:
          type: string
        priority:
          type: integer
        type:
          type: string
          enum: [seed, required, enhances]
        description:
          type: string
        instructions:
          type: string
        permissions:
          type: array
          items:
            $ref: '#/components/schemas/Permission'
        tool_call_schema:
          type: object
    
    Permission:
      type: object
      properties:
        resource:
          type: string
        action:
          type: string
        target:
          type: string
    
    ResponseMeta:
      type: object
      required:
        - request_id
        - timestamp
        - version
      properties:
        request_id:
          type: string
        timestamp:
          type: string
          format: date-time
        version:
          type: string
        latency_ms:
          type: integer
    
    ErrorResponse:
      type: object
      required:
        - error
        - meta
      properties:
        error:
          type: object
          required:
            - type
            - code
            - message
          properties:
            type:
              type: string
            code:
              type: string
            message:
              type: string
            details:
              type: object
            suggestion:
              type: string
        meta:
          $ref: '#/components/schemas/ResponseMeta'
    
    ListSkillsResponse:
      type: object
      properties:
        data:
          type: object
          properties:
            skills:
              type: array
              items:
                $ref: '#/components/schemas/SkillSummary'
            pagination:
              $ref: '#/components/schemas/Pagination'
        meta:
          $ref: '#/components/schemas/ResponseMeta'
    
    SkillSummary:
      type: object
      properties:
        skill_id:
          type: string
        version:
          type: string
        intent_description:
          type: string
        is_deprecated:
          type: boolean
        execution_success_rate:
          type: number
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time
    
    Pagination:
      type: object
      properties:
        page:
          type: integer
        page_size:
          type: integer
        total_count:
          type: integer
        total_pages:
          type: integer
    
    CreateSkillRequest:
      type: object
      required:
        - skill_id
        - version
        - intent_description
        - permissions
      properties:
        skill_id:
          type: string
          pattern: '^[a-z0-9_-]+:[a-z0-9_-]+$'
        version:
          type: string
          pattern: '^\\d+\\.\\d+\\.\\d+$'
        intent_description:
          type: string
          minLength: 50
          maxLength: 500
        permissions:
          type: array
          items:
            type: string
          minItems: 1
        trigger_conditions:
          type: object
        topology_hints:
          type: object
          properties:
            requires:
              type: array
              items:
                type: string
            conflicts_with:
              type: array
              items:
                type: string
            enhances:
              type: array
              items:
                type: string
            substitutes:
              type: array
              items:
                type: string
        content:
          type: string
    
    CreateSkillResponse:
      type: object
      properties:
        data:
          type: object
          properties:
            skill_id:
              type: string
            status:
              type: string
              enum: [pending, active, rejected]
            validation_result:
              type: object
            created_at:
              type: string
              format: date-time
        meta:
          $ref: '#/components/schemas/ResponseMeta'
    
    GetSkillResponse:
      type: object
      properties:
        data:
          $ref: '#/components/schemas/SkillDetail'
        meta:
          $ref: '#/components/schemas/ResponseMeta'
    
    SkillDetail:
      type: object
      properties:
        skill_id:
          type: string
        version:
          type: string
        intent_description:
          type: string
        permissions:
          type: array
          items:
            $ref: '#/components/schemas/Permission'
        trigger_conditions:
          type: object
        topology_hints:
          type: object
        execution_success_rate:
          type: number
        execution_count:
          type: integer
        is_deprecated:
          type: boolean
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time
        edges:
          type: object
    
    UpdateSkillRequest:
      type: object
      required:
        - version
        - intent_description
        - permissions
      properties:
        version:
          type: string
        intent_description:
          type: string
        permissions:
          type: array
          items:
            type: string
        trigger_conditions:
          type: object
        topology_hints:
          type: object
        content:
          type: string
    
    UpdateSkillResponse:
      type: object
      properties:
        data:
          type: object
          properties:
            skill_id:
              type: string
            updated_at:
              type: string
              format: date-time
        meta:
          $ref: '#/components/schemas/ResponseMeta'
    
    DeleteSkillResponse:
      type: object
      properties:
        data:
          type: object
          properties:
            skill_id:
              type: string
            is_deprecated:
              type: boolean
            deprecated_at:
              type: string
              format: date-time
            deprecation_reason:
              type: string
        meta:
          $ref: '#/components/schemas/ResponseMeta'
    
    HealthResponse:
      type: object
      properties:
        data:
          type: object
          properties:
            status:
              type: string
              enum: [healthy, degraded, unhealthy]
            components:
              type: object
              properties:
                graph_db:
                  type: object
                vector_db:
                  type: object
                redis:
                  type: object
                kafka:
                  type: object
            version:
              type: string
            uptime_seconds:
              type: integer
        meta:
          $ref: '#/components/schemas/ResponseMeta'
```

---

## 11. 版本历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| 1.0.0 | 2026-04-12 | 初始版本发布 | GraphSkill Architecture Team |
| 1.1.0 | 2026-04-17 | VR-First 架构适配：RoutingResponse 新增 enhancement_result 和 fallback_metadata 字段 | GraphSkill Architecture Team |

---

**文档结束**

*本文档定义了 GraphSkill 系统的 API 接口规范。相关数据结构定义详见 [RFC-08: 数据结构与 Schema 定义](RFC-08-data-structures-schema.md)，安全与权限模型详见 [RFC-11: 安全与权限模型](RFC-11-security-permission-model.md)。*