# RabbitMQ分布式部署指南

## 概述

LangBot现在支持基于RabbitMQ的分布式架构，允许将微信机器人客户端部署在多台机器上，统一由LangBot核心处理消息和AI推理。

## 架构图

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   机器 A        │    │   RabbitMQ      │    │   LangBot 核心   │
│                 │    │   消息队列      │    │                 │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ 微信客户端 1    │◄──►│ incoming_msgs   │◄──►│ AI 推理引擎     │
│ 微信客户端 2    │    │ outgoing_msgs   │    │ 插件系统        │
└─────────────────┘    │ client_status   │    │ 业务逻辑        │
                       └─────────────────┘    └─────────────────┘
┌─────────────────┐                          
│   机器 B        │                          
├─────────────────┤                          
│ 微信客户端 3    │◄──► 同一队列集合
│ 微信客户端 4    │     
└─────────────────┘     
```

## 部署步骤

### 1. 安装RabbitMQ

#### 使用Docker部署RabbitMQ

```bash
# 拉取RabbitMQ镜像
docker pull rabbitmq:3-management

# 启动RabbitMQ容器
docker run -d \
  --name langbot-rabbitmq \
  -p 5672:5672 \
  -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=langbot \
  -e RABBITMQ_DEFAULT_PASS=your_password \
  rabbitmq:3-management

# 访问管理界面
# http://localhost:15672
# 用户名: langbot
# 密码: your_password
```

#### 本地安装RabbitMQ

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install rabbitmq-server

# CentOS/RHEL
sudo yum install epel-release
sudo yum install rabbitmq-server

# macOS
brew install rabbitmq

# 启动服务
sudo systemctl start rabbitmq-server
sudo systemctl enable rabbitmq-server

# 启用管理插件
sudo rabbitmq-plugins enable rabbitmq_management
```

### 2. 配置LangBot

#### 服务端配置 (LangBot核心)

在 `config.yaml` 中添加RabbitMQ配置：

```yaml
# config.yaml
rabbitmq:
  host: "your_rabbitmq_host"
  port: 5672
  username: "langbot"
  password: "your_password"
  virtual_host: "/"

distributed:
  enabled: true
  server_mode:
    enabled: true
    load_balancing:
      strategy: "round_robin"
```

#### 客户端配置 (微信机器人)

```yaml
# client_config.yaml
rabbitmq:
  host: "your_rabbitmq_host"
  port: 5672
  username: "langbot"
  password: "your_password"

distributed:
  enabled: true
  client_mode:
    enabled: true
    client_id: "wecom_client_001"
    platform_type: "wecom"

# 微信配置保持不变
wecom:
  corpid: "your_corp_id"
  secret: "your_secret"
  token: "your_token"
  EncodingAESKey: "your_encoding_aes_key"
  contacts_secret: "your_contacts_secret"
  host: "0.0.0.0"
  port: 8080
```

### 3. 启动服务

#### 启动LangBot核心 (服务端)

```bash
# 在LangBot主服务器上
python -m examples.rabbitmq_example server
```

#### 启动微信客户端

```bash
# 在每台客户端机器上
python -m examples.rabbitmq_example client
```

## 配置选项

### RabbitMQ连接配置

```yaml
rabbitmq:
  host: "localhost"              # RabbitMQ服务器地址
  port: 5672                     # 端口
  username: "guest"              # 用户名
  password: "guest"              # 密码
  virtual_host: "/"              # 虚拟主机
  connection_timeout: 30         # 连接超时
  heartbeat: 60                  # 心跳间隔
```

### 分布式配置

```yaml
distributed:
  enabled: true                  # 启用分布式模式
  
  # 服务端配置
  server_mode:
    enabled: true
    load_balancing:
      strategy: "round_robin"    # 负载均衡策略
      # 可选: round_robin, least_connections, random
    
  # 客户端配置
  client_mode:
    enabled: false
    client_id: "auto"            # 客户端ID，auto表示自动生成
    platform_type: "wecom"      # 平台类型
```

## 监控与管理

### RabbitMQ管理界面

访问 `http://your_rabbitmq_host:15672` 查看：
- 队列状态
- 消息流量
- 连接状态
- 客户端信息

### 关键队列

- `incoming_messages`: 客户端发送的消息
- `outgoing_messages`: 发送给客户端的消息  
- `client_registry`: 客户端注册和心跳

### 日志监控

```bash
# 查看LangBot核心日志
tail -f logs/langbot.log

# 查看客户端日志
tail -f logs/client.log
```

## 扩展和优化

### 多平台支持

可以同时部署多种平台的客户端：

```bash
# WeChat客户端
python -m examples.rabbitmq_example client --platform wecom

# QQ客户端  
python -m examples.rabbitmq_example client --platform qq

# Telegram客户端
python -m examples.rabbitmq_example client --platform telegram
```

### 高可用部署

#### RabbitMQ集群

```bash
# 配置RabbitMQ集群以提高可用性
# 详见RabbitMQ官方文档
```

#### 多实例LangBot核心

```bash
# 启动多个LangBot核心实例进行负载分担
python -m examples.rabbitmq_example server --instance 1
python -m examples.rabbitmq_example server --instance 2
```

### 性能调优

```yaml
# 队列配置优化
rabbitmq:
  queues:
    incoming_messages:
      durable: true
      ttl: 300000
      max_length: 10000        # 队列最大长度
    
    outgoing_messages:
      durable: true
      ttl: 300000
      prefetch_count: 10       # 预取消息数量
```

## 故障排除

### 常见问题

1. **连接失败**
   ```bash
   # 检查RabbitMQ状态
   sudo systemctl status rabbitmq-server
   
   # 检查端口
   netstat -tulpn | grep 5672
   ```

2. **消息堆积**
   ```bash
   # 查看队列长度
   rabbitmqctl list_queues
   
   # 清理队列
   rabbitmqctl purge_queue incoming_messages
   ```

3. **客户端离线**
   ```bash
   # 检查客户端心跳
   # 在RabbitMQ管理界面查看连接状态
   ```

### 调试模式

```bash
# 启用详细日志
export LANGBOT_LOG_LEVEL=DEBUG
python -m examples.rabbitmq_example server
```

## 安全考虑

1. **网络安全**
   - 使用SSL/TLS加密RabbitMQ连接
   - 限制RabbitMQ访问IP
   - 使用防火墙保护端口

2. **认证授权**
   - 为每个客户端创建独立的RabbitMQ用户
   - 设置队列访问权限
   - 定期轮换密码

3. **消息安全**
   - 敏感消息加密传输
   - 消息内容过滤
   - 审计日志记录