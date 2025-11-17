import quart
from datetime import datetime

from .. import group


@group.group_class('messages', '/api/v1/messages')
class MessagesRouterGroup(group.RouterGroup):
    """Message history and proactive messaging API"""
    
    async def initialize(self) -> None:
        @self.route('/history', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def get_message_history() -> str:
            """Get message history with filters
            
            Query parameters:
            - bot_uuid: Filter by bot UUID
            - launcher_type: Filter by launcher type (person/group)
            - launcher_id: Filter by launcher ID
            - sender_id: Filter by sender ID
            - pipeline_uuid: Filter by pipeline UUID
            - limit: Maximum number of messages (default: 100, max: 1000)
            - offset: Offset for pagination (default: 0)
            - since: ISO datetime string to filter messages after this time
            """
            from ....api.http.service import message as message_service
            
            msg_service = message_service.MessageHistoryService(self.ap)
            
            # Parse query parameters
            bot_uuid = quart.request.args.get('bot_uuid')
            launcher_type = quart.request.args.get('launcher_type')
            launcher_id = quart.request.args.get('launcher_id')
            sender_id = quart.request.args.get('sender_id')
            pipeline_uuid = quart.request.args.get('pipeline_uuid')
            limit = min(int(quart.request.args.get('limit', 100)), 1000)
            offset = int(quart.request.args.get('offset', 0))
            since_str = quart.request.args.get('since')
            
            since = None
            if since_str:
                try:
                    since = datetime.fromisoformat(since_str)
                except ValueError:
                    return self.http_status(400, -1, 'Invalid datetime format for since parameter')
            
            try:
                messages = await msg_service.get_conversation_history(
                    bot_uuid=bot_uuid,
                    launcher_type=launcher_type,
                    launcher_id=launcher_id,
                    sender_id=sender_id,
                    pipeline_uuid=pipeline_uuid,
                    limit=limit,
                    offset=offset,
                    since=since,
                )
                
                return self.success(data={'messages': messages, 'count': len(messages)})
            except Exception as e:
                return self.http_status(500, -1, f'Failed to get message history: {str(e)}')

        @self.route('/history/inactive', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def get_inactive_conversations() -> str:
            """Get inactive conversations
            
            Query parameters:
            - bot_uuid: Filter by bot UUID
            - inactive_hours: Hours of inactivity (default: 24)
            - limit: Maximum number of conversations (default: 50, max: 200)
            """
            from ....api.http.service import message as message_service
            
            msg_service = message_service.MessageHistoryService(self.ap)
            
            bot_uuid = quart.request.args.get('bot_uuid')
            inactive_hours = int(quart.request.args.get('inactive_hours', 24))
            limit = min(int(quart.request.args.get('limit', 50)), 200)
            
            try:
                conversations = await msg_service.get_inactive_conversations(
                    bot_uuid=bot_uuid,
                    inactive_hours=inactive_hours,
                    limit=limit,
                )
                
                return self.success(data={'conversations': conversations, 'count': len(conversations)})
            except Exception as e:
                return self.http_status(500, -1, f'Failed to get inactive conversations: {str(e)}')

        @self.route('/history/delete', methods=['DELETE'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def delete_conversation_history() -> str:
            """Delete conversation history
            
            Required JSON body:
            - bot_uuid: Bot UUID
            - launcher_type: Launcher type (person/group)
            - launcher_id: Launcher ID
            """
            from ....api.http.service import message as message_service
            
            msg_service = message_service.MessageHistoryService(self.ap)
            
            try:
                data = await quart.request.json
                bot_uuid = data.get('bot_uuid')
                launcher_type = data.get('launcher_type')
                launcher_id = data.get('launcher_id')
                
                if not bot_uuid or not launcher_type or not launcher_id:
                    return self.http_status(400, -1, 'bot_uuid, launcher_type, and launcher_id are required')
                
                count = await msg_service.delete_conversation_history(
                    bot_uuid=bot_uuid,
                    launcher_type=launcher_type,
                    launcher_id=launcher_id,
                )
                
                return self.success(data={'deleted_count': count})
            except Exception as e:
                return self.http_status(500, -1, f'Failed to delete conversation history: {str(e)}')

        @self.route('/send', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def send_proactive_message() -> str:
            """Send proactive message to a user or group
            
            Required JSON body:
            - bot_uuid: Bot UUID
            - target_type: Target type ('person' or 'group')
            - target_id: Target ID (user ID or group ID)
            - message: Message content (string or message chain array)
            - pipeline_uuid: Optional pipeline UUID to use
            
            Example message chain:
            [
                {"type": "Plain", "text": "Hello!"},
                {"type": "Image", "url": "https://example.com/image.jpg"}
            ]
            """
            try:
                data = await quart.request.json
                bot_uuid = data.get('bot_uuid')
                target_type = data.get('target_type')
                target_id = data.get('target_id')
                message = data.get('message')
                pipeline_uuid = data.get('pipeline_uuid')
                
                if not bot_uuid or not target_type or not target_id or not message:
                    return self.http_status(400, -1, 'bot_uuid, target_type, target_id, and message are required')
                
                if target_type not in ['person', 'group']:
                    return self.http_status(400, -1, 'target_type must be "person" or "group"')
                
                # Find the bot
                bot = None
                for b in self.ap.platform_mgr.bots:
                    if b.uuid == bot_uuid:
                        bot = b
                        break
                
                if not bot:
                    return self.http_status(404, -1, 'Bot not found or not running')
                
                # Construct message chain
                import langbot_plugin.api.entities.builtin.platform.message as platform_message
                
                if isinstance(message, str):
                    message_chain = platform_message.MessageChain([
                        platform_message.Plain(text=message)
                    ])
                elif isinstance(message, list):
                    # Convert list of dicts to message components
                    components = []
                    for item in message:
                        msg_type = item.get('type')
                        if msg_type == 'Plain':
                            components.append(platform_message.Plain(text=item.get('text', '')))
                        elif msg_type == 'Image':
                            components.append(platform_message.Image(url=item.get('url', '')))
                        # Add more message types as needed
                    message_chain = platform_message.MessageChain(components)
                else:
                    return self.http_status(400, -1, 'message must be a string or array')
                
                # Send the message
                await bot.adapter.send_message(
                    target_type=target_type,
                    target_id=str(target_id),
                    message=message_chain,
                )
                
                # Save to message history
                from ....api.http.service import message as message_service
                msg_service = message_service.MessageHistoryService(self.ap)
                
                launcher_type_value = 'person' if target_type == 'person' else 'group'
                await msg_service.save_message(
                    bot_uuid=bot_uuid,
                    pipeline_uuid=pipeline_uuid or '',
                    launcher_type=launcher_type_value,
                    launcher_id=target_id,
                    sender_id=bot_uuid,
                    message_role='assistant',
                    message_content=str(message_chain),
                    message_chain=[component.__dict__ for component in message_chain],
                )
                
                return self.success(data={'message': 'Message sent successfully'})
                
            except Exception as e:
                self.ap.logger.error(f'Failed to send proactive message: {e}')
                import traceback
                self.ap.logger.error(traceback.format_exc())
                return self.http_status(500, -1, f'Failed to send proactive message: {str(e)}')
