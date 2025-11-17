# 消息历史与主动消息推送 API

LangBot 现在会自动将所有对话消息存储到数据库中，并提供了查询历史消息和主动发送消息给用户的 API。

## 功能特性

- **自动消息存储**：所有用户和助手的消息都会自动保存到数据库
- **消息历史查询**：使用灵活的过滤器检索对话历史
- **非活跃对话检测**：查找在指定时间内没有收到消息的对话
- **主动消息推送**：通过编程方式向用户或群组发送消息
- **对话管理**：在需要时删除对话历史

## 认证

所有消息 API 都需要通过以下方式之一进行认证：
- 用户令牌：`Authorization: Bearer <user_jwt_token>`
- API 密钥：`X-API-Key: lbk_your_api_key_here` 或 `Authorization: Bearer lbk_your_api_key_here`

有关 API 密钥认证的详细信息，请参阅 [API_KEY_AUTH.md](./API_KEY_AUTH.md)。

## API 端点

### 1. 查询消息历史

使用灵活的过滤选项检索对话历史。

**端点**：`GET /api/v1/messages/history`

**查询参数**：
- `bot_uuid`（可选）：按机器人 UUID 过滤
- `launcher_type`（可选）：按启动器类型过滤（`person` 或 `group`）
- `launcher_id`（可选）：按启动器 ID 过滤（用户 ID 或群组 ID）
- `sender_id`（可选）：按发送者 ID 过滤
- `pipeline_uuid`（可选）：按流水线 UUID 过滤
- `limit`（可选）：最大消息数量（默认：100，最大：1000）
- `offset`（可选）：分页偏移量（默认：0）
- `since`（可选）：ISO 日期时间字符串，用于过滤此时间之后的消息

**请求示例**：
```bash
curl -X GET "http://localhost:5300/api/v1/messages/history?bot_uuid=abc123&launcher_type=person&launcher_id=user456&limit=50" \
  -H "X-API-Key: lbk_your_api_key_here"
```

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "messages": [
      {
        "id": 123,
        "bot_uuid": "abc123",
        "pipeline_uuid": "pipeline789",
        "launcher_type": "person",
        "launcher_id": "user456",
        "sender_id": "user456",
        "message_role": "user",
        "message_content": "你好，你好吗？",
        "message_chain": [
          {"type": "Plain", "text": "你好，你好吗？"}
        ],
        "query_id": 1,
        "created_at": "2024-11-17T10:30:00",
        "updated_at": "2024-11-17T10:30:00"
      },
      {
        "id": 124,
        "bot_uuid": "abc123",
        "pipeline_uuid": "pipeline789",
        "launcher_type": "person",
        "launcher_id": "user456",
        "sender_id": "abc123",
        "message_role": "assistant",
        "message_content": "我很好，谢谢！",
        "message_chain": [
          {"type": "Plain", "text": "我很好，谢谢！"}
        ],
        "query_id": 1,
        "created_at": "2024-11-17T10:30:05",
        "updated_at": "2024-11-17T10:30:05"
      }
    ],
    "count": 2
  }
}
```

### 2. 获取非活跃对话

查找在指定时间段内处于非活跃状态的对话。

**端点**：`GET /api/v1/messages/history/inactive`

**查询参数**：
- `bot_uuid`（可选）：按机器人 UUID 过滤
- `inactive_hours`（可选）：非活跃时长（小时）（默认：24）
- `limit`（可选）：最大对话数量（默认：50，最大：200）

**请求示例**：
```bash
curl -X GET "http://localhost:5300/api/v1/messages/history/inactive?bot_uuid=abc123&inactive_hours=48&limit=10" \
  -H "X-API-Key: lbk_your_api_key_here"
```

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "conversations": [
      {
        "bot_uuid": "abc123",
        "launcher_type": "person",
        "launcher_id": "user456",
        "last_message_time": "2024-11-15T10:30:00"
      },
      {
        "bot_uuid": "abc123",
        "launcher_type": "group",
        "launcher_id": "group789",
        "last_message_time": "2024-11-14T15:20:00"
      }
    ],
    "count": 2
  }
}
```

### 3. 发送主动消息

通过编程方式向用户或群组发送消息。

**端点**：`POST /api/v1/messages/send`

**请求体**：
- `bot_uuid`（必填）：发送消息的机器人 UUID
- `target_type`（必填）：目标类型（`person` 或 `group`）
- `target_id`（必填）：目标 ID（用户 ID 或群组 ID）
- `message`（必填）：消息内容（字符串或消息链数组）
- `pipeline_uuid`（可选）：与此消息关联的流水线 UUID

**请求示例（简单文本）**：
```bash
curl -X POST "http://localhost:5300/api/v1/messages/send" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: lbk_your_api_key_here" \
  -d '{
    "bot_uuid": "abc123",
    "target_type": "person",
    "target_id": "user456",
    "message": "你好！我们注意到您最近不太活跃。一切都还好吗？"
  }'
```

**请求示例（消息链）**：
```bash
curl -X POST "http://localhost:5300/api/v1/messages/send" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: lbk_your_api_key_here" \
  -d '{
    "bot_uuid": "abc123",
    "target_type": "person",
    "target_id": "user456",
    "message": [
      {"type": "Plain", "text": "你好！看看这张图片："},
      {"type": "Image", "url": "https://example.com/image.jpg"}
    ]
  }'
```

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "message": "Message sent successfully"
  }
}
```

### 4. 删除对话历史

删除特定对话的所有消息历史。

**端点**：`DELETE /api/v1/messages/history/delete`

**请求体**：
- `bot_uuid`（必填）：机器人 UUID
- `launcher_type`（必填）：启动器类型（`person` 或 `group`）
- `launcher_id`（必填）：启动器 ID

**请求示例**：
```bash
curl -X DELETE "http://localhost:5300/api/v1/messages/history/delete" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: lbk_your_api_key_here" \
  -d '{
    "bot_uuid": "abc123",
    "launcher_type": "person",
    "launcher_id": "user456"
  }'
```

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "deleted_count": 42
  }
}
```

## 使用场景

### 1. 重新激活非活跃用户

检查非活跃对话并发送主动消息：

```python
import requests

API_BASE = "http://localhost:5300/api/v1"
API_KEY = "lbk_your_api_key_here"
headers = {"X-API-Key": API_KEY}

# 获取非活跃对话（48 小时内无活动）
response = requests.get(
    f"{API_BASE}/messages/history/inactive",
    params={"inactive_hours": 48, "limit": 10},
    headers=headers
)

inactive_convs = response.json()["data"]["conversations"]

# 向每个对话发送重新激活消息
for conv in inactive_convs:
    requests.post(
        f"{API_BASE}/messages/send",
        json={
            "bot_uuid": conv["bot_uuid"],
            "target_type": conv["launcher_type"],
            "target_id": conv["launcher_id"],
            "message": "你好！我们注意到您最近不太活跃。有什么我们可以帮助的吗？"
        },
        headers=headers
    )
```

### 2. 定时提醒

根据消息历史向用户发送定时提醒：

```python
import requests
from datetime import datetime, timedelta

API_BASE = "http://localhost:5300/api/v1"
API_KEY = "lbk_your_api_key_here"
headers = {"X-API-Key": API_KEY}

# 获取最近 7 天的消息
since_date = (datetime.now() - timedelta(days=7)).isoformat()
response = requests.get(
    f"{API_BASE}/messages/history",
    params={
        "bot_uuid": "abc123",
        "launcher_type": "person",
        "since": since_date
    },
    headers=headers
)

messages = response.json()["data"]["messages"]

# 分析消息并根据内容发送提醒
# （在此处实现您的逻辑）
```

### 3. 分析和报告

查询消息历史进行分析：

```python
import requests
from collections import Counter

API_BASE = "http://localhost:5300/api/v1"
API_KEY = "lbk_your_api_key_here"
headers = {"X-API-Key": API_KEY}

# 获取所有最近的消息
response = requests.get(
    f"{API_BASE}/messages/history",
    params={"limit": 1000},
    headers=headers
)

messages = response.json()["data"]["messages"]

# 按启动器类型统计消息
launcher_types = Counter(msg["launcher_type"] for msg in messages)
print(f"个人消息：{launcher_types['person']}")
print(f"群组消息：{launcher_types['group']}")

# 统计用户和助手消息
roles = Counter(msg["message_role"] for msg in messages)
print(f"用户消息：{roles['user']}")
print(f"助手消息：{roles['assistant']}")
```

## 数据库结构

`message_history` 表的结构如下：

| 列名 | 类型 | 描述 |
|------|------|------|
| id | Integer | 主键，自增 |
| bot_uuid | String(255) | 机器人 UUID（已索引）|
| pipeline_uuid | String(255) | 流水线 UUID（已索引，可为空）|
| launcher_type | String(50) | 启动器类型：'person' 或 'group'（已索引）|
| launcher_id | String(255) | 启动器 ID（已索引）|
| sender_id | String(255) | 发送者 ID（已索引）|
| message_role | String(50) | 消息角色：'user' 或 'assistant' |
| message_content | Text | 消息的字符串表示 |
| message_chain | JSON | JSON 格式的完整消息链 |
| query_id | Integer | 来自流水线的查询 ID（可为空）|
| created_at | DateTime | 消息创建时间戳（已索引）|
| updated_at | DateTime | 最后更新时间戳 |

## 安全考虑

- **需要认证**：所有端点都需要有效的用户令牌或 API 密钥
- **机器人隔离**：消息按机器人 UUID 过滤以防止跨机器人数据访问
- **速率限制**：考虑为主动消息实施速率限制以防止垃圾消息
- **数据隐私**：消息历史包含敏感的用户数据；确保适当的访问控制
- **SQL 注入保护**：所有查询都使用参数化语句

## 性能提示

- 对大结果集的分页使用适当的 `limit` 和 `offset`
- 查询历史时使用 `since` 参数限制日期范围
- 在 `bot_uuid`、`launcher_type`、`launcher_id` 和 `created_at` 上的索引确保快速查询
- 对于非常高流量的机器人，考虑定期归档旧消息

## 迁移

数据库迁移（`dbm012`）在 LangBot 启动时自动应用。数据库版本从 11 更新到 12。

如果需要手动检查迁移状态，请连接到您的数据库并检查 `metadata` 表：

```sql
SELECT * FROM metadata WHERE key = 'database_version';
```

## 常见问题

**Q: 消息会占用多少存储空间？**

A: 每条消息大约占用 1-2KB，具体取决于消息内容和链的复杂度。对于高流量机器人，建议定期归档或清理旧消息。

**Q: 可以禁用自动消息存储吗？**

A: 当前版本中，消息存储是自动启用的。如果需要禁用，可以修改 `src/langbot/pkg/pipeline/respback/respback.py` 文件。

**Q: 消息存储会影响性能吗？**

A: 消息存储是异步的，对性能影响很小。即使保存失败，也不会中断正常的消息处理流程。

**Q: 如何备份消息历史？**

A: 可以使用标准的数据库备份工具（如 SQLite 的 `.backup` 命令或 PostgreSQL 的 `pg_dump`）来备份整个数据库，包括消息历史。
