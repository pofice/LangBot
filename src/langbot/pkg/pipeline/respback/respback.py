from __future__ import annotations

import random
import asyncio


import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message

from .. import stage, entities
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from ...api.http.service import message as message_service


@stage.stage_class('SendResponseBackStage')
class SendResponseBackStage(stage.PipelineStage):
    """发送响应消息"""

    async def process(self, query: pipeline_query.Query, stage_inst_name: str) -> entities.StageProcessResult:
        """处理"""

        # Save user message to database
        msg_service = message_service.MessageHistoryService(self.ap)
        try:
            # Save user's message
            user_message_chain = [component.__dict__ for component in query.message_chain]
            await msg_service.save_message(
                bot_uuid=query.bot_uuid,
                pipeline_uuid=query.pipeline_uuid or '',
                launcher_type=query.launcher_type.value,
                launcher_id=query.launcher_id,
                sender_id=query.sender_id,
                message_role='user',
                message_content=str(query.message_chain),
                message_chain=user_message_chain,
                query_id=query.query_id,
            )
        except Exception as e:
            self.ap.logger.error(f'Failed to save user message to database: {e}')

        random_range = (
            query.pipeline_config['output']['force-delay']['min'],
            query.pipeline_config['output']['force-delay']['max'],
        )

        random_delay = random.uniform(*random_range)

        self.ap.logger.debug('根据规则强制延迟回复: %s s', random_delay)

        await asyncio.sleep(random_delay)

        if query.pipeline_config['output']['misc']['at-sender'] and isinstance(
            query.message_event, platform_events.GroupMessage
        ):
            query.resp_message_chain[-1].insert(0, platform_message.At(target=query.message_event.sender.id))

        quote_origin = query.pipeline_config['output']['misc']['quote-origin']

        has_chunks = any(isinstance(msg, provider_message.MessageChunk) for msg in query.resp_messages)
        # TODO 命令与流式的兼容性问题
        if await query.adapter.is_stream_output_supported() and has_chunks:
            is_final = [msg.is_final for msg in query.resp_messages][0]
            await query.adapter.reply_message_chunk(
                message_source=query.message_event,
                bot_message=query.resp_messages[-1],
                message=query.resp_message_chain[-1],
                quote_origin=quote_origin,
                is_final=is_final,
            )
        else:
            await query.adapter.reply_message(
                message_source=query.message_event,
                message=query.resp_message_chain[-1],
                quote_origin=quote_origin,
            )

        # Save assistant's response to database
        try:
            assistant_message_chain = [component.__dict__ for component in query.resp_message_chain[-1]]
            await msg_service.save_message(
                bot_uuid=query.bot_uuid,
                pipeline_uuid=query.pipeline_uuid or '',
                launcher_type=query.launcher_type.value,
                launcher_id=query.launcher_id,
                sender_id=query.bot_uuid,  # Bot is the sender of assistant messages
                message_role='assistant',
                message_content=str(query.resp_message_chain[-1]),
                message_chain=assistant_message_chain,
                query_id=query.query_id,
            )
        except Exception as e:
            self.ap.logger.error(f'Failed to save assistant message to database: {e}')

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
