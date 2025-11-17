# Message History and Proactive Messaging API

LangBot now automatically stores all conversation messages to the database and provides APIs for querying history and sending proactive messages to users.

## Features

- **Automatic Message Storage**: All user and assistant messages are automatically saved to the database
- **Message History Query**: Retrieve conversation history with flexible filters
- **Inactive Conversation Detection**: Find conversations that haven't received messages for a specified time
- **Proactive Messaging**: Send messages to users or groups programmatically
- **Conversation Management**: Delete conversation history when needed

## Authentication

All message APIs require authentication via either:
- User Token: `Authorization: Bearer <user_jwt_token>`
- API Key: `X-API-Key: lbk_your_api_key_here` or `Authorization: Bearer lbk_your_api_key_here`

See [API_KEY_AUTH.md](./API_KEY_AUTH.md) for details on API key authentication.

## API Endpoints

### 1. Query Message History

Retrieve conversation history with flexible filtering options.

**Endpoint**: `GET /api/v1/messages/history`

**Query Parameters**:
- `bot_uuid` (optional): Filter by bot UUID
- `launcher_type` (optional): Filter by launcher type (`person` or `group`)
- `launcher_id` (optional): Filter by launcher ID (user ID or group ID)
- `sender_id` (optional): Filter by sender ID
- `pipeline_uuid` (optional): Filter by pipeline UUID
- `limit` (optional): Maximum number of messages (default: 100, max: 1000)
- `offset` (optional): Offset for pagination (default: 0)
- `since` (optional): ISO datetime string to filter messages after this time

**Example Request**:
```bash
curl -X GET "http://localhost:5300/api/v1/messages/history?bot_uuid=abc123&launcher_type=person&launcher_id=user456&limit=50" \
  -H "X-API-Key: lbk_your_api_key_here"
```

**Example Response**:
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
        "message_content": "Hello, how are you?",
        "message_chain": [
          {"type": "Plain", "text": "Hello, how are you?"}
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
        "message_content": "I'm doing well, thank you!",
        "message_chain": [
          {"type": "Plain", "text": "I'm doing well, thank you!"}
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

### 2. Get Inactive Conversations

Find conversations that have been inactive for a specified period.

**Endpoint**: `GET /api/v1/messages/history/inactive`

**Query Parameters**:
- `bot_uuid` (optional): Filter by bot UUID
- `inactive_hours` (optional): Hours of inactivity (default: 24)
- `limit` (optional): Maximum number of conversations (default: 50, max: 200)

**Example Request**:
```bash
curl -X GET "http://localhost:5300/api/v1/messages/history/inactive?bot_uuid=abc123&inactive_hours=48&limit=10" \
  -H "X-API-Key: lbk_your_api_key_here"
```

**Example Response**:
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

### 3. Send Proactive Message

Send a message to a user or group programmatically.

**Endpoint**: `POST /api/v1/messages/send`

**Request Body**:
- `bot_uuid` (required): Bot UUID to send from
- `target_type` (required): Target type (`person` or `group`)
- `target_id` (required): Target ID (user ID or group ID)
- `message` (required): Message content (string or message chain array)
- `pipeline_uuid` (optional): Pipeline UUID to associate with this message

**Example Request (Simple Text)**:
```bash
curl -X POST "http://localhost:5300/api/v1/messages/send" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: lbk_your_api_key_here" \
  -d '{
    "bot_uuid": "abc123",
    "target_type": "person",
    "target_id": "user456",
    "message": "Hello! We noticed you haven'\''t been active lately. Is everything okay?"
  }'
```

**Example Request (Message Chain)**:
```bash
curl -X POST "http://localhost:5300/api/v1/messages/send" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: lbk_your_api_key_here" \
  -d '{
    "bot_uuid": "abc123",
    "target_type": "person",
    "target_id": "user456",
    "message": [
      {"type": "Plain", "text": "Hello! Check out this image:"},
      {"type": "Image", "url": "https://example.com/image.jpg"}
    ]
  }'
```

**Example Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "message": "Message sent successfully"
  }
}
```

### 4. Delete Conversation History

Delete all message history for a specific conversation.

**Endpoint**: `DELETE /api/v1/messages/history/delete`

**Request Body**:
- `bot_uuid` (required): Bot UUID
- `launcher_type` (required): Launcher type (`person` or `group`)
- `launcher_id` (required): Launcher ID

**Example Request**:
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

**Example Response**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "deleted_count": 42
  }
}
```

## Use Cases

### 1. Re-engage Inactive Users

Check for inactive conversations and send proactive messages:

```python
import requests

API_BASE = "http://localhost:5300/api/v1"
API_KEY = "lbk_your_api_key_here"
headers = {"X-API-Key": API_KEY}

# Get inactive conversations (no activity in 48 hours)
response = requests.get(
    f"{API_BASE}/messages/history/inactive",
    params={"inactive_hours": 48, "limit": 10},
    headers=headers
)

inactive_convs = response.json()["data"]["conversations"]

# Send re-engagement message to each
for conv in inactive_convs:
    requests.post(
        f"{API_BASE}/messages/send",
        json={
            "bot_uuid": conv["bot_uuid"],
            "target_type": conv["launcher_type"],
            "target_id": conv["launcher_id"],
            "message": "Hi! We noticed you haven't been active lately. How can we help?"
        },
        headers=headers
    )
```

### 2. Scheduled Reminders

Send scheduled reminders to users based on message history:

```python
import requests
from datetime import datetime, timedelta

API_BASE = "http://localhost:5300/api/v1"
API_KEY = "lbk_your_api_key_here"
headers = {"X-API-Key": API_KEY}

# Get messages from last 7 days
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

# Analyze messages and send reminders based on content
# (implement your logic here)
```

### 3. Analytics and Reporting

Query message history for analytics:

```python
import requests
from collections import Counter

API_BASE = "http://localhost:5300/api/v1"
API_KEY = "lbk_your_api_key_here"
headers = {"X-API-Key": API_KEY}

# Get all recent messages
response = requests.get(
    f"{API_BASE}/messages/history",
    params={"limit": 1000},
    headers=headers
)

messages = response.json()["data"]["messages"]

# Count messages by launcher type
launcher_types = Counter(msg["launcher_type"] for msg in messages)
print(f"Person messages: {launcher_types['person']}")
print(f"Group messages: {launcher_types['group']}")

# Count user vs assistant messages
roles = Counter(msg["message_role"] for msg in messages)
print(f"User messages: {roles['user']}")
print(f"Assistant messages: {roles['assistant']}")
```

## Database Schema

The `message_history` table has the following structure:

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key, auto-increment |
| bot_uuid | String(255) | Bot UUID (indexed) |
| pipeline_uuid | String(255) | Pipeline UUID (indexed, nullable) |
| launcher_type | String(50) | Launcher type: 'person' or 'group' (indexed) |
| launcher_id | String(255) | Launcher ID (indexed) |
| sender_id | String(255) | Sender ID (indexed) |
| message_role | String(50) | Message role: 'user' or 'assistant' |
| message_content | Text | String representation of message |
| message_chain | JSON | Full message chain in JSON format |
| query_id | Integer | Query ID from pipeline (nullable) |
| created_at | DateTime | Message creation timestamp (indexed) |
| updated_at | DateTime | Last update timestamp |

## Security Considerations

- **Authentication Required**: All endpoints require valid user token or API key
- **Bot Isolation**: Messages are filtered by bot UUID to prevent cross-bot data access
- **Rate Limiting**: Consider implementing rate limits for proactive messaging to prevent spam
- **Data Privacy**: Message history contains sensitive user data; ensure proper access controls
- **SQL Injection Protection**: All queries use parameterized statements

## Performance Tips

- Use appropriate `limit` and `offset` for pagination of large result sets
- Use `since` parameter to limit date range when querying history
- Index on `bot_uuid`, `launcher_type`, `launcher_id`, and `created_at` ensures fast queries
- Consider periodic archival of old messages for very high-volume bots

## Migration

The database migration (`dbm012`) is automatically applied when LangBot starts. The database version is updated from 11 to 12.

If you need to manually check the migration status, connect to your database and check the `metadata` table:

```sql
SELECT * FROM metadata WHERE key = 'database_version';
```
