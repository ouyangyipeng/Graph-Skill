# RFC-09: 部署与运维规范

**文档编号:** RFC-09  
**版本:** 1.0.0  
**状态:** 正式发布  
**最后更新:** 2026-04-12  
**作者:** GraphSkill Architecture Team  
**分类:** 架构规范 - 运维部署  
**依赖:** RFC-00, RFC-06

---

## 目录

1. [概述](#1-概述)
2. [容器化部署策略](#2-容器化部署策略)
3. [Kubernetes Helm Chart 配置](#3-kubernetes-helm-chart-配置)
4. [服务发现与注册](#4-服务发现与注册)
5. [配置管理](#5-配置管理)
6. [日志规范](#6-日志规范)
7. [监控告警体系](#7-监控告警体系)
8. [运维手册](#8-运维手册)
9. [生产环境部署检查清单](#9-生产环境部署检查清单)
10. [故障排查指南](#10-故障排查指南)
11. [版本历史](#11-版本历史)

---

## 1. 概述

### 1.1 文档目的

本文档定义 GraphSkill 系统的部署与运维规范，涵盖容器化部署策略、Kubernetes Helm Chart 配置、服务发现与注册、配置管理、日志规范、监控告警体系、运维手册、生产环境部署检查清单以及故障排查指南。

### 1.2 适用范围

本文档适用于：
- DevOps 工程师：执行部署与运维操作
- SRE 工程师：规划高可用与容灾策略
- 平台工程师：配置 Kubernetes 集群
- 运维团队：日常运维与故障处理

### 1.3 部署架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Deployment Architecture                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Kubernetes Cluster                               │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                     Namespace: graphskill                    │    │   │
│  │  │                                                              │    │   │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │    │   │
│  │  │  │ Routing     │  │ Routing     │  │ Routing     │           │    │   │
│  │  │  │ Gateway     │  │ Gateway     │  │ Gateway     │           │    │   │
│  │  │  │ (Pod)       │  │ (Pod)       │  │ (Pod)       │           │    │   │
│  │  │  └─────────────┘  └─────────────┘  └─────────────┘           │    │   │
│  │  │                                                              │    │   │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │    │   │
│  │  │  │ Ingestion   │  │ Ingestion   │  │ Telemetry   │           │    │   │
│  │  │  │ Engine      │  │ Engine      │  │ Consumer    │           │    │   │
│  │  │  │ (Pod)       │  │ (Pod)       │  │ (Pod)       │           │    │   │
│  │  │  └─────────────┘  └─────────────┘  └─────────────┘           │    │   │
│  │  │                                                              │    │   │
│  │  │  ┌─────────────────────────────────────────────────────┐    │    │   │
│  │  │  │                     StatefulSets                     │    │    │   │
│  │  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │    │    │   │
│  │  │  │  │ Neo4j       │  │ Milvus      │  │ Redis       │  │    │    │   │
│  │  │  │  │ (Primary)   │  │ (Cluster)   │  │ (Cluster)   │  │    │    │   │
│  │  │  │  └─────────────┘  └─────────────┘  └─────────────┘  │    │    │   │
│  │  │  └─────────────────────────────────────────────────────┘    │    │   │
│  │  │                                                              │    │   │
│  │  │  ┌─────────────────────────────────────────────────────┐    │    │   │
│  │  │  │                     ConfigMaps & Secrets             │    │    │   │
│  │  │  └─────────────────────────────────────────────────────┘    │    │   │
│  │  │                                                              │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                     Ingress Controller                       │    │   │
│  │  │  ┌─────────────┐                                              │    │   │
│  │  │  │ nginx-ingress│  → api.graphskill.io                        │    │   │
│  │  │  └─────────────┘                                              │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     External Services                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Kafka       │  │ Prometheus  │  │ Grafana     │  │ ELK Stack   │ │   │
│  │  │ Cluster     │  │             │  │             │  │             │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.4 部署环境定义

| 环境 | 用途 | 配置规模 | 命名空间 |
|------|------|----------|----------|
| **Development** | 开发调试 | 单节点，最小配置 | `graphskill-dev` |
| **Staging** | 预发布测试 | 多节点，中等配置 | `graphskill-staging` |
| **Production** | 生产运行 | 多节点，高可用配置 | `graphskill` |

---

## 2. 容器化部署策略

### 2.1 Docker 镜像规范

#### 2.1.1 镜像命名规范

```
# 镜像命名格式
graphskill/{service_name}:{version}-{environment}

# 示例
graphskill/routing-gateway:1.0.0-prod
graphskill/ingestion-engine:1.0.0-prod
graphskill/telemetry-consumer:1.0.0-prod
```

#### 2.1.2 Dockerfile 规范

```dockerfile
# Routing Gateway Dockerfile (Go)

# Build Stage
FROM golang:1.21-alpine AS builder

WORKDIR /app

# 安装依赖
RUN apk add --no-cache git make

# 复制源码
COPY go.mod go.sum ./
RUN go mod download

COPY . .

# 构建
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o routing-gateway ./cmd/gateway

# Runtime Stage
FROM alpine:3.19

WORKDIR /app

# 安装运行时依赖
RUN apk add --no-cache ca-certificates tzdata

# 复制构建产物
COPY --from=builder /app/routing-gateway .
COPY --from=builder /app/config ./config

# 创建非 root 用户
RUN addgroup -S graphskill && adduser -S graphskill -G graphskill
USER graphskill

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

# 暴露端口
EXPOSE 8080 9090

# 启动命令
ENTRYPOINT ["./routing-gateway"]
CMD ["--config", "./config/gateway.yaml"]
```

```dockerfile
# Ingestion Engine Dockerfile (Python)

# Build Stage
FROM python:3.11-slim AS builder

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime Stage
FROM python:3.11-slim

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制 Python 包
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# 复制源码
COPY src ./src
COPY config ./config

# 创建非 root 用户
RUN useradd -m -s /bin/bash graphskill
USER graphskill

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# 暴露端口
EXPOSE 8080

# 启动命令
ENTRYPOINT ["python", "-m", "src.ingestion.engine"]
CMD ["--config", "./config/ingestion.yaml"]
```

### 2.2 镜像构建规范

```yaml
# docker-compose.build.yaml

services:
  routing-gateway:
    build:
      context: ./services/routing-gateway
      dockerfile: Dockerfile
      args:
        VERSION: ${VERSION:-1.0.0}
        ENVIRONMENT: ${ENVIRONMENT:-prod}
    image: graphskill/routing-gateway:${VERSION:-1.0.0}-${ENVIRONMENT:-prod}
    
  ingestion-engine:
    build:
      context: ./services/ingestion-engine
      dockerfile: Dockerfile
      args:
        VERSION: ${VERSION:-1.0.0}
        ENVIRONMENT: ${ENVIRONMENT:-prod}
    image: graphskill/ingestion-engine:${VERSION:-1.0.0}-${ENVIRONMENT:-prod}
    
  telemetry-consumer:
    build:
      context: ./services/telemetry-consumer
      dockerfile: Dockerfile
      args:
        VERSION: ${VERSION:-1.0.0}
        ENVIRONMENT: ${ENVIRONMENT:-prod}
    image: graphskill/telemetry-consumer:${VERSION:-1.0.0}-${ENVIRONMENT:-prod}
```

### 2.3 镜像安全规范

| 规范 | 描述 |
|------|------|
| **最小化基础镜像** | MUST 使用 alpine 或 slim 镜像 |
| **非 root 用户** | MUST 使用非 root 用户运行 |
| **镜像扫描** | MUST 在构建后执行安全扫描 |
| **签名验证** | SHOULD 使用镜像签名验证 |
| **敏感数据** | MUST NOT 在镜像中硬编码敏感数据 |

---

## 3. Kubernetes Helm Chart 配置

### 3.1 Helm Chart 结构

```
graphskill-chart/
├── Chart.yaml
├── values.yaml
├── values-dev.yaml
├── values-staging.yaml
├── values-prod.yaml
├── templates/
│   ├── _helpers.tpl
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml
│   ├── routing-gateway/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── hpa.yaml
│   │   └── pdb.yaml
│   ├── ingestion-engine/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── hpa.yaml
│   ├── telemetry-consumer/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   ├── neo4j/
│   │   ├── statefulset.yaml
│   │   ├── service.yaml
│   │   └── pvc.yaml
│   ├── milvus/
│   │   ├── statefulset.yaml
│   │   ├── service.yaml
│   │   └── pvc.yaml
│   ├── redis/
│   │   ├── statefulset.yaml
│   │   ├── service.yaml
│   │   └── pvc.yaml
│   ├── ingress.yaml
│   └── networkpolicy.yaml
└── charts/
    ├── neo4j-5.12.0.tgz
    ├── milvus-4.1.0.tgz
    └── redis-7.2.0.tgz
```

### 3.2 Chart.yaml

```yaml
apiVersion: v2
name: graphskill
description: GraphSkill - Topology-Aware Procedural Knowledge Routing for LLM Agents
type: application
version: 1.0.0
appVersion: "1.0.0"

maintainers:
  - name: GraphSkill Team
    email: team@graphskill.io
    url: https://graphskill.io

dependencies:
  - name: neo4j
    version: "5.12.0"
    repository: "https://helm.neo4j.com"
    condition: neo4j.enabled
    
  - name: milvus
    version: "4.1.0"
    repository: "https://milvus.io/charts"
    condition: milvus.enabled
    
  - name: redis
    version: "7.2.0"
    repository: "https://charts.bitnami.com/bitnami"
    condition: redis.enabled

keywords:
  - llm
  - agent
  - rag
  - graph
  - routing
  - skills

home: https://graphskill.io
sources:
  - https://github.com/graphskill/graphskill

annotations:
  artifacthub.io/license: Apache-2.0
  artifacthub.io/signKey: |
    fingerprint: "..."
    url: "https://graphskill.io/signing.key"
```

### 3.3 values.yaml（默认配置）

```yaml
# Global Configuration
global:
  imageRegistry: docker.io
  imagePullSecrets: []
  storageClass: standard
  environment: production
  logLevel: info
  version: 1.0.0

# Namespace
namespace:
  create: true
  name: graphskill

# Routing Gateway Configuration
routingGateway:
  enabled: true
  replicaCount: 3
  
  image:
    repository: graphskill/routing-gateway
    tag: 1.0.0-prod
    pullPolicy: IfNotPresent
  
  service:
    type: ClusterIP
    port: 8080
    grpcPort: 9090
  
  resources:
    limits:
      cpu: 2000m
      memory: 4Gi
    requests:
      cpu: 500m
      memory: 1Gi
  
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70
    targetMemoryUtilizationPercentage: 80
  
  podDisruptionBudget:
    enabled: true
    minAvailable: 2
  
  affinity:
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          podAffinityTerm:
            labelSelector:
              matchLabels:
                app: routing-gateway
            topologyKey: kubernetes.io/hostname
  
  tolerations: []
  
  nodeSelector: {}
  
  config:
    graphDbHost: neo4j
    graphDbPort: 7687
    vectorDbHost: milvus
    vectorDbPort: 19530
    redisHost: redis-master
    redisPort: 6379
    cacheEnabled: true
    fallbackEnabled: true

# Ingestion Engine Configuration
ingestionEngine:
  enabled: true
  replicaCount: 2
  
  image:
    repository: graphskill/ingestion-engine
    tag: 1.0.0-prod
    pullPolicy: IfNotPresent
  
  service:
    type: ClusterIP
    port: 8080
  
  resources:
    limits:
      cpu: 1000m
      memory: 2Gi
    requests:
      cpu: 250m
      memory: 512Mi
  
  config:
    llmApiEndpoint: https://api.openai.com/v1
    llmModel: gpt-4o
    batchSize: 50
    parallelWorkers: 4

# Telemetry Consumer Configuration
telemetryConsumer:
  enabled: true
  replicaCount: 2
  
  image:
    repository: graphskill/telemetry-consumer
    tag: 1.0.0-prod
    pullPolicy: IfNotPresent
  
  resources:
    limits:
      cpu: 500m
      memory: 1Gi
    requests:
      cpu: 100m
      memory: 256Mi
  
  config:
    kafkaBrokers: kafka:9092
    consumerGroup: graphskill-telemetry
    topics:
      - graphskill_telemetry
      - graphskill_evolution

# Neo4j Configuration
neo4j:
  enabled: true
  
  nameOverride: neo4j
  
  serverConfig:
    dbms.memory.heap.initial_size: "2G"
    dbms.memory.heap.max_size: "4G"
    dbms.memory.pagecache.size: "1G"
  
  persistence:
    enabled: true
    size: 50Gi
    storageClass: standard
  
  resources:
    limits:
      cpu: 4000m
      memory: 8Gi
    requests:
      cpu: 1000m
      memory: 4Gi
  
  service:
    type: ClusterIP
    ports:
      http: 7474
      bolt: 7687

# Milvus Configuration
milvus:
  enabled: true
  
  nameOverride: milvus
  
  cluster:
    enabled: true
  
  components:
    proxy:
      replicas: 2
    queryNode:
      replicas: 2
    dataNode:
      replicas: 2
  
  persistence:
    enabled: true
    storageClass: standard
    size: 100Gi
  
  resources:
    proxy:
      limits:
        cpu: 1000m
        memory: 2Gi
    queryNode:
      limits:
        cpu: 2000m
        memory: 4Gi
    dataNode:
      limits:
        cpu: 1000m
        memory: 2Gi

# Redis Configuration
redis:
  enabled: true
  
  nameOverride: redis
  
  architecture: replication
  
  master:
    replicas: 1
    resources:
      limits:
        cpu: 500m
        memory: 1Gi
  
  replica:
    replicas: 2
    resources:
      limits:
        cpu: 250m
        memory: 512Mi
  
  sentinel:
    enabled: true
    replicas: 3
  
  persistence:
    enabled: true
    size: 10Gi

# Kafka Configuration (External)
kafka:
  enabled: false  # 使用外部 Kafka
  
  external:
    brokers: "kafka-01:9092,kafka-02:9092,kafka-03:9092"

# Ingress Configuration
ingress:
  enabled: true
  
  className: nginx
  
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "60"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "60"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  
  hosts:
    - host: api.graphskill.io
      paths:
        - path: /
          pathType: Prefix
          service: routing-gateway
          port: 8080
  
  tls:
    - secretName: graphskill-tls
      hosts:
        - api.graphskill.io

# Network Policy
networkPolicy:
  enabled: true
  
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: nginx-ingress
      ports:
        - port: 8080
          protocol: TCP
  
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: neo4j
      ports:
        - port: 7687
          protocol: TCP
    - to:
        - podSelector:
            matchLabels:
              app: milvus
      ports:
        - port: 19530
          protocol: TCP

# Monitoring Configuration
monitoring:
  enabled: true
  
  prometheus:
    enabled: true
    serviceMonitor:
      enabled: true
      interval: 30s
      namespace: monitoring
  
  grafana:
    enabled: true
    dashboards:
      enabled: true
      namespace: monitoring

# Logging Configuration
logging:
  enabled: true
  
  fluentd:
    enabled: true
  
  elasticsearch:
    enabled: false  # 使用外部 ELK

# Security Configuration
security:
  podSecurityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000
  
  containerSecurityContext:
    allowPrivilegeEscalation: false
    capabilities:
      drop:
        - ALL
    readOnlyRootFilesystem: true
```

### 3.4 values-prod.yaml（生产环境配置）

```yaml
# Production Environment Overrides

global:
  environment: production
  logLevel: warn

routingGateway:
  replicaCount: 5
  
  resources:
    limits:
      cpu: 4000m
      memory: 8Gi
    requests:
      cpu: 1000m
      memory: 2Gi
  
  autoscaling:
    minReplicas: 5
    maxReplicas: 20
    targetCPUUtilizationPercentage: 60

ingestionEngine:
  replicaCount: 3
  
  resources:
    limits:
      cpu: 2000m
      memory: 4Gi

neo4j:
  serverConfig:
    dbms.memory.heap.initial_size: "4G"
    dbms.memory.heap.max_size: "8G"
    dbms.memory.pagecache.size: "2G"
  
  persistence:
    size: 200Gi
  
  resources:
    limits:
      cpu: 8000m
      memory: 16Gi

milvus:
  components:
    proxy:
      replicas: 3
    queryNode:
      replicas: 4
    dataNode:
      replicas: 3
  
  persistence:
    size: 500Gi

redis:
  master:
    resources:
      limits:
        cpu: 1000m
        memory: 2Gi
  
  replica:
    replicas: 3
```

### 3.5 部署命令

```bash
# 安装 Helm Chart
helm install graphskill ./graphskill-chart \
  -n graphskill \
  --create-namespace \
  -f values-prod.yaml

# 升级部署
helm upgrade graphskill ./graphskill-chart \
  -n graphskill \
  -f values-prod.yaml \
  --atomic \
  --timeout 10m

# 回滚部署
helm rollback graphskill 1 -n graphskill

# 卸载部署
helm uninstall graphskill -n graphskill
```

---

## 4. 服务发现与注册

### 4.1 Kubernetes Service 配置

```yaml
# Routing Gateway Service
apiVersion: v1
kind: Service
metadata:
  name: routing-gateway
  namespace: graphskill
  labels:
    app: routing-gateway
spec:
  type: ClusterIP
  ports:
    - name: http
      port: 8080
      targetPort: 8080
      protocol: TCP
    - name: grpc
      port: 9090
      targetPort: 9090
      protocol: TCP
  selector:
    app: routing-gateway

---
# Routing Gateway Headless Service (用于 Pod 间直接通信)
apiVersion: v1
kind: Service
metadata:
  name: routing-gateway-headless
  namespace: graphskill
  labels:
    app: routing-gateway
spec:
  type: ClusterIP
  clusterIP: None
  ports:
    - name: http
      port: 8080
      targetPort: 8080
      protocol: TCP
  selector:
    app: routing-gateway
```

### 4.2 服务端点配置

| 服务 | 端点 | 端口 | 协议 |
|------|------|------|------|
| routing-gateway | `routing-gateway.graphskill.svc.cluster.local` | 8080 | HTTP |
| routing-gateway-grpc | `routing-gateway.graphskill.svc.cluster.local` | 9090 | gRPC |
| ingestion-engine | `ingestion-engine.graphskill.svc.cluster.local` | 8080 | HTTP |
| neo4j-bolt | `neo4j.graphskill.svc.cluster.local` | 7687 | Bolt |
| neo4j-http | `neo4j.graphskill.svc.cluster.local` | 7474 | HTTP |
| milvus | `milvus.graphskill.svc.cluster.local` | 19530 | gRPC |
| redis | `redis-master.graphskill.svc.cluster.local` | 6379 | TCP |

### 4.3 DNS 配置规范

```yaml
# CoreDNS 配置 (用于服务发现)
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    graphskill.svc.cluster.local:53 {
      errors
      health
      ready
      kubernetes graphskill.svc.cluster.local in-addr.arpa ip6.arpa {
        pods insecure
        fallthrough in-addr.arpa ip6.arpa
      }
      prometheus :9153
      forward . /etc/resolv.conf
      cache 30
      loop
      reload
      loadbalance
    }
```

---

## 5. 配置管理

### 5.1 ConfigMap 定义

```yaml
# Routing Gateway ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: routing-gateway-config
  namespace: graphskill
data:
  gateway.yaml: |
    server:
      http:
        port: 8080
        read_timeout: 30s
        write_timeout: 30s
      grpc:
        port: 9090
        max_connection_age: 30s
    
    databases:
      graph:
        host: neo4j.graphskill.svc.cluster.local
        port: 7687
        username: neo4j
        max_connections: 50
        connection_timeout: 5s
      
      vector:
        host: milvus.graphskill.svc.cluster.local
        port: 19530
        collection: skill_vectors
      
      redis:
        host: redis-master.graphskill.svc.cluster.local
        port: 6379
        db: 0
    
    routing:
      cache:
        enabled: true
        ttl: 3600s
        max_entries: 10000
      
      fallback:
        enabled: true
        timeout_threshold: 500ms
      
      scoring:
        alpha: 0.5
        beta: 0.3
        gamma: 0.2
    
    logging:
      level: info
      format: json
      output: stdout
    
    telemetry:
      enabled: true
      kafka:
        brokers: kafka-01:9092,kafka-02:9092,kafka-03:9092
        topic: graphskill_telemetry

---
# Ingestion Engine ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: ingestion-engine-config
  namespace: graphskill
data:
  ingestion.yaml: |
    parser:
      file_patterns:
        - "*.md"
        - "SKILL.md"
      exclude_patterns:
        - "*.tmp"
        - "*.bak"
    
    llm:
      api_endpoint: https://api.openai.com/v1
      model: gpt-4o
      temperature: 0.3
      max_tokens: 2000
    
    topology:
      inference:
        enabled: true
        confidence_threshold: 0.85
      dag_validation:
        enabled: true
    
    batch:
      size: 50
      parallel_workers: 4
      timeout: 300s
    
    logging:
      level: info
      format: json
```

### 5.2 Secrets 定义

```yaml
# Database Secrets
apiVersion: v1
kind: Secret
metadata:
  name: database-secrets
  namespace: graphskill
type: Opaque
stringData:
  neo4j-password: "change-me-in-production"
  redis-password: "change-me-in-production"
  milvus-password: ""

---
# LLM API Secrets
apiVersion: v1
kind: Secret
metadata:
  name: llm-api-secrets
  namespace: graphskill
type: Opaque
stringData:
  openai-api-key: "change-me-in-production"
  openai-organization: ""

---
# JWT Signing Secrets
apiVersion: v1
kind: Secret
metadata:
  name: jwt-secrets
  namespace: graphskill
type: Opaque
stringData:
  jwt-private-key: |
    -----BEGIN RSA PRIVATE KEY-----
    change-me-in-production
    -----END RSA PRIVATE KEY-----
  jwt-public-key: |
    -----BEGIN RSA PUBLIC KEY-----
    change-me-in-production
    -----END RSA PUBLIC KEY-----
```

### 5.3 配置热更新策略

系统 SHOULD 支持配置热更新，无需重启服务：

```yaml
# ConfigMap 挂载方式
apiVersion: apps/v1
kind: Deployment
metadata:
  name: routing-gateway
spec:
  template:
    spec:
      containers:
        - name: routing-gateway
          volumeMounts:
            - name: config
              mountPath: /app/config
              readOnly: true
      volumes:
        - name: config
          configMap:
            name: routing-gateway-config
            optional: false
```

---

## 6. 日志规范

### 6.1 日志格式定义

系统 MUST 使用结构化 JSON 日志格式：

```json
{
  "timestamp": "2026-04-12T10:00:00.123Z",
  "level": "info",
  "service": "routing-gateway",
  "trace_id": "trace_abc123",
  "session_id": "sess_abc123",
  "message": "Routing request completed",
  "context": {
    "query_hash": "sha256:abc123",
    "skill_count": 5,
    "latency_ms": 285,
    "routing_mode": "normal"
  },
  "error": null,
  "stack_trace": null,
  "metadata": {
    "hostname": "routing-gateway-01",
    "version": "1.0.0",
    "environment": "production"
  }
}
```

### 6.2 日志级别规范

| 级别 | 用途 | 示例场景 |
|------|------|----------|
| **DEBUG** | 调试信息（仅开发环境） | 详细执行流程 |
| **INFO** | 正常运行信息 | 请求处理、状态变更 |
| **WARN** | 警告信息（不影响运行） | 降级触发、缓存失效 |
| **ERROR** | 错误信息（影响单请求） | 请求失败、数据库错误 |
| **FATAL** | 致命错误（影响系统） | 服务启动失败、配置错误 |

### 6.3 日志配置

```yaml
# Logging Configuration
logging:
  format: json
  level: info
  output: stdout
  
  # 字段过滤
  fields:
    include:
      - timestamp
      - level
      - service
      - trace_id
      - message
      - context
    exclude:
      - password
      - token
      - secret
      - api_key
  
  # 采样配置（高流量场景）
  sampling:
    enabled: true
    rate: 0.1  # 10% 采样率
    threshold: 1000  # QPS > 1000 时启用
  
  # 日志轮转
  rotation:
    enabled: false  # Kubernetes 环境使用容器日志
```

### 6.4 Fluentd 配置

```yaml
# Fluentd ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluentd-config
  namespace: graphskill
data:
  fluent.conf: |
    <source>
      @type tail
      path /var/log/containers/*.log
      pos_file /var/log/fluentd-containers.log.pos
      tag kubernetes.*
      read_from_head true
      <parse>
        @type json
        time_key timestamp
        time_format %Y-%m-%dT%H:%M:%S.%NZ
      </parse>
    </source>
    
    <filter kubernetes.**>
      @type parser
      key_name log
      reserve_data true
      <parse>
        @type json
      </parse>
    </filter>
    
    <match kubernetes.graphskill.**>
      @type elasticsearch
      host elasticsearch.logging.svc.cluster.local
      port 9200
      logstash_format true
      logstash_prefix graphskill
      include_tag_key true
      tag_key @log_name
      flush_interval 5s
    </match>
```

---

## 7. 监控告警体系

### 7.1 Prometheus ServiceMonitor 配置

```yaml
# ServiceMonitor for Routing Gateway
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: routing-gateway
  namespace: monitoring
  labels:
    app: routing-gateway
spec:
  selector:
    matchLabels:
      app: routing-gateway
  namespaceSelector:
    matchNames:
      - graphskill
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
      scrapeTimeout: 10s

---
# ServiceMonitor for Ingestion Engine
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: ingestion-engine
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: ingestion-engine
  namespaceSelector:
    matchNames:
      - graphskill
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
```

### 7.2 PrometheusRule 配置

```yaml
# PrometheusRule for GraphSkill
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: graphskill-rules
  namespace: monitoring
spec:
  groups:
    - name: graphskill.routing
      rules:
        - alert: RoutingLatencyHigh
          expr: histogram_quantile(0.99, sum(rate(graphskill_routing_latency_seconds_bucket[5m])) by (le)) > 0.5
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Routing latency P99 exceeds 500ms"
            description: "Routing latency P99 is {{ $value }}s"
        
        - alert: RoutingErrorRateHigh
          expr: sum(rate(graphskill_routing_requests_total{status="error"}[5m])) / sum(rate(graphskill_routing_requests_total[5m])) > 0.01
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Routing error rate exceeds 1%"
        
        - alert: RoutingFallbackRateHigh
          expr: sum(rate(graphskill_routing_fallbacks_total[5m])) / sum(rate(graphskill_routing_requests_total[5m])) > 0.05
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Routing fallback rate exceeds 5%"
        
        - alert: RoutingServiceDown
          expr: up{job="routing-gateway"} == 0
          for: 1m
          labels:
            severity: critical
          annotations:
            summary: "Routing Gateway service is down"
    
    - name: graphskill.database
      rules:
        - alert: Neo4jConnectionPoolExhausted
          expr: neo4j_connection_pool_active_connections / neo4j_connection_pool_max_connections > 0.8
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Neo4j connection pool utilization exceeds 80%"
        
        - alert: MilvusLatencyHigh
          expr: histogram_quantile(0.95, sum(rate(milvus_search_latency_bucket[5m])) by (le)) > 0.2
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Milvus search latency P95 exceeds 200ms"
        
        - alert: RedisMemoryHigh
          expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.8
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Redis memory utilization exceeds 80%"
    
    - name: graphskill.system
      rules:
        - alert: HighCPUUsage
          expr: sum(rate(container_cpu_usage_seconds_total{namespace="graphskill"}[5m])) by (pod) > 0.8
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Pod {{ $labels.pod }} CPU usage exceeds 80%"
        
        - alert: HighMemoryUsage
          expr: sum(container_memory_working_set_bytes{namespace="graphskill"}) by (pod) / sum(container_spec_memory_limit_bytes{namespace="graphskill"}) by (pod) > 0.8
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Pod {{ $labels.pod }} memory usage exceeds 80%"
        
        - alert: PodCrashLooping
          expr: rate(kube_pod_container_status_restarts_total{namespace="graphskill"}[15m]) > 0.1
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Pod {{ $labels.pod }} is crash looping"
```

### 7.3 Grafana Dashboard 配置

```json
{
  "dashboard": {
    "title": "GraphSkill Operations Dashboard",
    "uid": "graphskill-ops",
    "tags": ["graphskill", "operations"],
    "panels": [
      {
        "title": "Routing Performance",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        "targets": [
          {
            "expr": "histogram_quantile(0.99, sum(rate(graphskill_routing_latency_seconds_bucket[5m])) by (le))",
            "legendFormat": "P99"
          },
          {
            "expr": "histogram_quantile(0.50, sum(rate(graphskill_routing_latency_seconds_bucket[5m])) by (le))",
            "legendFormat": "P50"
          }
        ]
      },
      {
        "title": "Request Rate",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
        "targets": [
          {
            "expr": "sum(rate(graphskill_routing_requests_total[5m]))",
            "legendFormat": "QPS"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "gauge",
        "gridPos": {"h": 4, "w": 6, "x": 0, "y": 8},
        "targets": [
          {
            "expr": "sum(rate(graphskill_routing_requests_total{status=\"error\"}[5m])) / sum(rate(graphskill_routing_requests_total[5m]))",
            "legendFormat": "Error Rate"
          }
        ],
        "thresholds": [
          {"value": 0.01, "color": "yellow"},
          {"value": 0.05, "color": "red"}
        ]
      },
      {
        "title": "Fallback Rate",
        "type": "gauge",
        "gridPos": {"h": 4, "w": 6, "x": 6, "y": 8},
        "targets": [
          {
            "expr": "sum(rate(graphskill_routing_fallbacks_total[5m])) / sum(rate(graphskill_routing_requests_total[5m]))",
            "legendFormat": "Fallback Rate"
          }
        ]
      },
      {
        "title": "Database Health",
        "type": "stat",
        "gridPos": {"h": 4, "w": 12, "x": 12, "y": 8},
        "targets": [
          {
            "expr": "up{job=\"neo4j\"}",
            "legendFormat": "Neo4j"
          },
          {
            "expr": "up{job=\"milvus\"}",
            "legendFormat": "Milvus"
          },
          {
            "expr": "up{job=\"redis\"}",
            "legendFormat": "Redis"
          }
        ]
      }
    ]
  }
}
```

---

## 8. 运维手册

### 8.1 日常运维任务

| 任务 | 频率 | 操作步骤 |
|------|------|----------|
| **健康检查** | 每小时 | 检查各服务状态、数据库连接 |
| **日志审查** | 每天 | 检查 ERROR/FATAL 日志 |
| **性能监控** | 每天 | 检查 P99 延迟、错误率 |
| **备份验证** | 每天 | 验证数据库备份完整性 |
| **容量规划** | 每周 | 检查资源使用趋势 |
| **安全审计** | 每月 | 检查访问日志、权限变更 |

### 8.2 扩容操作手册

```bash
# 手动扩容 Routing Gateway
kubectl scale deployment routing-gateway \
  -n graphskill \
  --replicas=10

# 自动扩容配置验证
kubectl get hpa routing-gateway -n graphskill

# 数据库扩容（Neo4j）
kubectl patch statefulset neo4j \
  -n graphskill \
  -p '{"spec":{"resources":{"limits":{"cpu":"8000m","memory":"16Gi"}}}}'

# 存储扩容
kubectl patch pvc neo4j-data \
  -n graphskill \
  -p '{"spec":{"resources":{"requests":{"storage":"200Gi"}}}}'
```

### 8.3 升级操作手册

```bash
# 1. 准备升级
# 检查当前版本
helm list -n graphskill

# 检查新版本镜像
docker pull graphskill/routing-gateway:1.1.0-prod

# 2. 执行升级
helm upgrade graphskill ./graphskill-chart \
  -n graphskill \
  -f values-prod.yaml \
  --set routingGateway.image.tag=1.1.0-prod \
  --atomic \
  --timeout 10m

# 3. 验证升级
kubectl rollout status deployment/routing-gateway -n graphskill

# 4. 健康检查
curl -f https://api.graphskill.io/v1/health

# 5. 监控观察
# 观察 10 分钟，确认无异常
```

### 8.4 回滚操作手册

```bash
# 1. 确认回滚版本
helm history graphskill -n graphskill

# 2. 执行回滚
helm rollback graphskill 1 -n graphskill

# 3. 验证回滚
kubectl rollout status deployment/routing-gateway -n graphskill

# 4. 健康检查
curl -f https://api.graphskill.io/v1/health
```

---

## 9. 生产环境部署检查清单

### 9.1 部署前检查清单

| 检查项 | 状态 | 说明 |
|--------|------|------|
| **镜像准备** | [ ] | 所有镜像已构建并推送到 Registry |
| **镜像扫描** | [ ] | 所有镜像已通过安全扫描 |
| **配置验证** | [ ] | ConfigMap 和 Secrets 已正确配置 |
| **资源预估** | [ ] | CPU/内存/存储资源已评估 |
| **网络配置** | [ ] | NetworkPolicy 已配置 |
| **DNS 配置** | [ ] | 服务 DNS 解析正常 |
| **证书配置** | [ ] | TLS 证书已配置 |
| **监控配置** | [ ] | Prometheus/Grafana 已配置 |
| **告警配置** | [ ] | 告警规则已配置 |
| **日志配置** | [ ] | 日志收集已配置 |
| **备份策略** | [ ] | 数据库备份策略已配置 |
| **容灾策略** | [ ] | 跨区域容灾已配置 |

### 9.2 部署后验证清单

| 检查项 | 状态 | 说明 |
|--------|------|------|
| **Pod 状态** | [ ] | 所有 Pod 处于 Running 状态 |
| **服务健康** | [ ] | `/health` 端点返回 healthy |
| **数据库连接** | [ ] | Neo4j/Milvus/Redis 连接正常 |
| **API 功能** | [ ] | `/v1/route` API 正常响应 |
| **性能基准** | [ ] | P99 延迟 < 500ms |
| **错误率** | [ ] | 错误率 < 0.1% |
| **日志输出** | [ ] | 日志正常输出到 ELK |
| **监控数据** | [ ] | Prometheus 正常采集指标 |
| **告警测试** | [ ] | 告警通知正常触发 |
| **备份验证** | [ ] | 数据库备份可恢复 |

---

## 10. 故障排查指南

### 10.1 常见故障分类

| 故障类型 | 症状 | 可能原因 |
|----------|------|----------|
| **服务启动失败** | Pod CrashLooping | 配置错误、资源不足、依赖服务不可用 |
| **数据库连接失败** | 连接超时 | 网络问题、认证失败、连接池耗尽 |
| **路由延迟高** | P99 > 500ms | 图数据库慢查询、向量检索慢、缓存失效 |
| **高错误率** | 错误率 > 1% | 参数校验失败、权限问题、内部错误 |
| **降级频繁** | fallback_rate > 5% | 图数据库不稳定、网络抖动 |
| **内存溢出** | OOM Killed | 内存泄漏、请求量过大 |

### 10.2 故障排查流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  发现故障   │────▶│  收集信息   │────▶│  定位原因   │────▶│  执行修复   │
│             │     │             │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  [告警/监控]        [日志/指标]         [分析/诊断]         [修复/验证]
```

### 10.3 故障排查命令

```bash
# Pod 状态检查
kubectl get pods -n graphskill
kubectl describe pod routing-gateway-xxx -n graphskill

# 日志查看
kubectl logs routing-gateway-xxx -n graphskill --tail=100
kubectl logs routing-gateway-xxx -n graphskill --previous  # 查看上一个容器日志

# 事件查看
kubectl get events -n graphskill --sort-by='.lastTimestamp'

# 资源使用检查
kubectl top pods -n graphskill
kubectl top nodes

# 网络连通性测试
kubectl exec -it routing-gateway-xxx -n graphskill -- curl neo4j:7687
kubectl exec -it routing-gateway-xxx -n graphskill -- curl milvus:19530

# 数据库连接检查
kubectl exec -it neo4j-0 -n graphskill -- cypher-shell "RETURN 1"

# 进入容器调试
kubectl exec -it routing-gateway-xxx -n graphskill -- /bin/sh

# 端口转发（本地调试）
kubectl port-forward svc/routing-gateway 8080:8080 -n graphskill
```

### 10.4 故障排查案例

#### 案例 1: Pod 启动失败

```bash
# 症状
kubectl get pods -n graphskill
# NAME                  READY   STATUS             RESTARTS   AGE
# routing-gateway-xxx   0/1     CrashLoopBackOff   5          10m

# 排查步骤
# 1. 查看 Pod 详情
kubectl describe pod routing-gateway-xxx -n graphskill

# 2. 查看容器日志
kubectl logs routing-gateway-xxx -n graphskill --previous

# 3. 常见原因
# - 配置错误：检查 ConfigMap
# - 资源不足：检查 resources limits
# - 依赖服务不可用：检查数据库状态

# 修复方案
# - 修正配置
# - 增加资源
# - 等待依赖服务恢复
```

#### 案例 2: 路由延迟高

```bash
# 症状
# Grafana 显示 P99 延迟 > 500ms

# 排查步骤
# 1. 检查各组件延迟
curl http://routing-gateway:8080/metrics | grep latency

# 2. 检查图数据库延迟
kubectl exec -it neo4j-0 -n graphskill -- cypher-shell "CALL dbms.listQueries()"

# 3. 检查向量数据库延迟
kubectl exec -it milvus-0 -n graphskill -- curl localhost:9091/metrics

# 4. 检查缓存命中率
curl http://routing-gateway:8080/metrics | grep cache_hit

# 修复方案
# - 优化图查询
# - 增加缓存
# - 扩容数据库
```

#### 案例 3: 数据库连接失败

```bash
# 症状
# 日志显示 "Connection refused" 或 "Timeout"

# 排查步骤
# 1. 检查数据库 Pod 状态
kubectl get pods -n graphskill -l app=neo4j

# 2. 检查数据库服务
kubectl get svc -n graphskill

# 3. 测试网络连通性
kubectl exec -it routing-gateway-xxx -n graphskill -- nc -zv neo4j 7687

# 4. 检查认证信息
kubectl get secret database-secrets -n graphskill -o jsonpath='{.data.neo4j-password}'

# 修复方案
# - 重启数据库 Pod
# - 检查认证配置
# - 检查 NetworkPolicy
```

---

## 11. 版本历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| 1.0.0 | 2026-04-12 | 初始版本发布 | GraphSkill Architecture Team |
| 1.1.0 | 2026-04-17 | VR-First 架构适配：配置参数更新 top_k=5, expansion_depth=1, α=0.8 | GraphSkill Architecture Team |

---

**文档结束**

*本文档定义了 GraphSkill 系统的部署与运维规范。相关性能与高可用规范详见 [RFC-06: 性能安全与高可用规范](RFC-06-performance-security-high-availability.md)，测试与质量保障规范详见 [RFC-10: 测试与质量保障规范](RFC-10-testing-quality-assurance.md)。*