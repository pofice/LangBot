# Message History and Proactive Messaging Implementation

## Overview

This implementation adds automatic message history storage to LangBot's database and provides comprehensive APIs for querying conversation history, detecting inactive conversations, and sending proactive messages to users.

## Problem Statement (Original Request)

The user wanted to know if LangBot saves user messages to the database, with the goal of:
1. Implementing proactive message sending to customers
2. Enabling the bot to reach out to customers who haven't replied in a while

**Original Request (Chinese):**
> LangBot是否会将用户消息保存至数据库,从而后续的我想要实现主动的发消息给客户
> 比如说有的客户有一段时间没回消息了,机器人去主动的出击

## Solution

This implementation provides a complete solution for:
- ✅ Automatic message storage to database
- ✅ Message history query with flexible filters
- ✅ Inactive conversation detection
- ✅ Proactive message sending API
- ✅ Conversation management

## Features

### 1. Automatic Message Storage
- All user and assistant messages are automatically saved during pipeline processing
- Stores complete message chains with metadata
- Non-blocking with error handling to prevent disruption
- Includes bot UUID, pipeline UUID, launcher info, sender info, and timestamps

### 2. Message History Query API
- Query history with filters: bot, launcher type/ID, sender, pipeline, time range
- Support for pagination (limit/offset)
- Returns complete message chains with all metadata
- Authentication required (user token or API key)

### 3. Inactive Conversation Detection
- Identify conversations inactive for X hours
- Efficient aggregate query
- Sorted by last activity time
- Perfect for re-engagement campaigns

### 4. Proactive Messaging
- Send messages programmatically via REST API
- Supports simple text and rich message chains (images, etc.)
- Messages automatically saved to history
- Can target individuals or groups

### 5. Conversation Management
- Delete conversation history when needed
- Returns count of deleted messages
- Useful for GDPR compliance or cleanup

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User/Platform                         │
└────────────┬────────────────────────────────────────────┘
             │
             │ Message In
             ▼
┌─────────────────────────────────────────────────────────┐
│              Platform Adapter Layer                      │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│                 Pipeline Processing                      │
│  ┌────────┐  ┌────────┐  ┌──────────────┐             │
│  │ Preproc│→ │Process │→ │SendResponse  │             │
│  │        │  │        │  │  BackStage   │             │
│  └────────┘  └────────┘  └──────┬───────┘             │
│                                  │                       │
│                      ┌───────────▼──────────┐           │
│                      │ Save User Message    │           │
│                      └───────────┬──────────┘           │
│                                  │                       │
│                      ┌───────────▼──────────┐           │
│                      │Send Response         │           │
│                      └───────────┬──────────┘           │
│                                  │                       │
│                      ┌───────────▼──────────┐           │
│                      │Save Assistant Message│           │
│                      └───────────┬──────────┘           │
└──────────────────────────────────┼──────────────────────┘
                                   │
                                   ▼
                    ┌────────────────────────┐
                    │  message_history       │
                    │  Table (SQLAlchemy)    │
                    └────────────────────────┘
                                   │
                                   │ Query
                                   ▼
                    ┌────────────────────────┐
                    │ MessageHistoryService  │
                    └──────────┬─────────────┘
                               │
                               ▼
                    ┌────────────────────────┐
                    │  REST API Endpoints    │
                    │ /api/v1/messages/*     │
                    └────────────────────────┘
```

## Database Schema

### message_history Table

| Column | Type | Nullable | Indexed | Description |
|--------|------|----------|---------|-------------|
| id | Integer | No | PK | Auto-increment primary key |
| bot_uuid | String(255) | No | Yes | Bot UUID |
| pipeline_uuid | String(255) | Yes | Yes | Pipeline UUID |
| launcher_type | String(50) | No | Yes | 'person' or 'group' |
| launcher_id | String(255) | No | Yes | User/group ID |
| sender_id | String(255) | No | Yes | Sender ID |
| message_role | String(50) | No | No | 'user' or 'assistant' |
| message_content | Text | No | No | String representation |
| message_chain | JSON | No | No | Full message chain |
| query_id | Integer | Yes | No | Pipeline query ID |
| created_at | DateTime | No | Yes | Creation timestamp |
| updated_at | DateTime | No | No | Update timestamp |

**Indexes:**
- Primary key on `id`
- Index on `bot_uuid` for filtering by bot
- Index on `launcher_type` for filtering by conversation type
- Index on `launcher_id` for filtering by conversation
- Index on `sender_id` for filtering by sender
- Index on `created_at` for time-based queries
- Index on `pipeline_uuid` for pipeline filtering

## API Endpoints

### 1. GET /api/v1/messages/history
Query message history with filters.

**Parameters:**
- bot_uuid, launcher_type, launcher_id, sender_id, pipeline_uuid
- limit (max 1000), offset
- since (ISO datetime)

### 2. GET /api/v1/messages/history/inactive
Get conversations inactive for X hours.

**Parameters:**
- bot_uuid, inactive_hours (default 24), limit (max 200)

### 3. POST /api/v1/messages/send
Send proactive message to user/group.

**Body:**
- bot_uuid, target_type, target_id, message, pipeline_uuid (optional)

### 4. DELETE /api/v1/messages/history/delete
Delete conversation history.

**Body:**
- bot_uuid, launcher_type, launcher_id

## Code Structure

```
src/langbot/pkg/
├── entity/persistence/
│   └── message.py                    # MessageHistory entity model
├── api/http/
│   ├── service/
│   │   └── message.py                # MessageHistoryService
│   └── controller/groups/
│       └── messages.py               # API endpoints
├── pipeline/
│   └── respback/
│       └── respback.py               # Updated to save messages
├── persistence/migrations/
│   └── dbm012_add_message_history.py # Database migration
└── utils/
    └── constants.py                  # DB version updated to 12

tests/unit_tests/
└── message/
    ├── __init__.py
    └── test_message_service.py       # Unit tests

docs/
├── MESSAGE_HISTORY_API.md            # English documentation
└── MESSAGE_HISTORY_API_ZH.md         # Chinese documentation
```

## Usage Examples

### Example 1: Find and Re-engage Inactive Users

```python
import requests
import schedule
import time

API_BASE = "http://localhost:5300/api/v1"
API_KEY = "lbk_your_api_key_here"

def check_and_reengage():
    # Get inactive conversations (48 hours)
    response = requests.get(
        f"{API_BASE}/messages/history/inactive",
        params={"inactive_hours": 48},
        headers={"X-API-Key": API_KEY}
    )
    
    inactive = response.json()["data"]["conversations"]
    
    # Send re-engagement message
    for conv in inactive:
        requests.post(
            f"{API_BASE}/messages/send",
            json={
                "bot_uuid": conv["bot_uuid"],
                "target_type": conv["launcher_type"],
                "target_id": conv["launcher_id"],
                "message": "Hi! We noticed you haven't been active. Need help?"
            },
            headers={"X-API-Key": API_KEY}
        )
        print(f"Re-engaged {conv['launcher_id']}")

# Run daily at 10 AM
schedule.every().day.at("10:00").do(check_and_reengage)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Example 2: Analyze Conversation Patterns

```python
import requests
from datetime import datetime, timedelta

API_BASE = "http://localhost:5300/api/v1"
API_KEY = "lbk_your_api_key_here"

# Get last 7 days of messages
since = (datetime.now() - timedelta(days=7)).isoformat()
response = requests.get(
    f"{API_BASE}/messages/history",
    params={"since": since, "limit": 1000},
    headers={"X-API-Key": API_KEY}
)

messages = response.json()["data"]["messages"]

# Analyze peak hours
from collections import Counter
hours = [datetime.fromisoformat(m["created_at"]).hour for m in messages]
peak_hours = Counter(hours).most_common(3)

print(f"Peak activity hours: {peak_hours}")
```

## Testing

### Unit Tests
```bash
# Run message service tests
pytest tests/unit_tests/message/

# Run all tests
pytest tests/
```

**Test Coverage:**
- ✅ Save message
- ✅ Get conversation history
- ✅ Get conversation history with filters
- ✅ Get inactive conversations
- ✅ Delete conversation history

**Test Results:** All 46 tests passing (41 existing + 5 new)

### Integration Testing

```bash
# Run integration test script
python /tmp/test_integration.py
```

## Security

- ✅ All endpoints require authentication (user token or API key)
- ✅ Messages filtered by bot UUID to prevent cross-bot access
- ✅ Parameterized SQL queries prevent injection
- ✅ Error handling prevents information leakage
- ✅ No vulnerabilities found by CodeQL

## Performance

- **Message Storage:** Asynchronous, non-blocking
- **Query Performance:** Optimized with indexes on key columns
- **Storage Impact:** ~1-2KB per message
- **Recommendations:**
  - Use pagination for large result sets
  - Use date filters to limit query scope
  - Consider archival for very high-volume bots

## Migration

Database migration from version 11 to 12 is automatic.

**Manual verification:**
```sql
SELECT * FROM metadata WHERE key = 'database_version';
-- Should return 12
```

## Future Enhancements

Potential improvements for future iterations:
- [ ] Webhook notifications for inactive conversations
- [ ] Scheduled task framework for automated re-engagement
- [ ] Full-text search on message content
- [ ] Message archival system
- [ ] Analytics dashboard
- [ ] Batch proactive messaging
- [ ] Message templates
- [ ] A/B testing for re-engagement messages

## Compatibility

- **LangBot Version:** 4.5.2+
- **Python:** 3.10+
- **Database:** SQLite (default), PostgreSQL, MySQL (via config)
- **Required Dependencies:** All included in standard LangBot installation

## Support

For issues or questions:
- Documentation: `docs/MESSAGE_HISTORY_API.md` (English) or `docs/MESSAGE_HISTORY_API_ZH.md` (Chinese)
- Unit Tests: `tests/unit_tests/message/`
- GitHub Issues: https://github.com/pofice/LangBot/issues

## License

This implementation follows LangBot's existing license.
