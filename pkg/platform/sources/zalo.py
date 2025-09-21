from __future__ import annotations

import typing
import asyncio
import traceback
import datetime

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
from langbot_plugin.api.entities.builtin.command import errors as command_errors

from libs.zalo_api import ZaloClient
from libs.zalo_api.zaloevent import ZaloEvent

from ..logger import EventLogger


class ZaloMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain):
        contents: list[dict] = []
        for msg in message_chain:
            if type(msg) is platform_message.Plain:
                contents.append({'type': 'text', 'content': msg.text})
        return contents

    @staticmethod
    async def target2yiri(message: str, message_id: str):
        parts: list[platform_message.MessageComponent] = []
        parts.append(platform_message.Source(id=message_id, time=datetime.datetime.now()))
        parts.append(platform_message.Plain(text=message))
        return platform_message.MessageChain(parts)


class ZaloEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent) -> ZaloEvent:
        return event.source_platform_object

    @staticmethod
    async def target2yiri(event: ZaloEvent):
        chain = await ZaloMessageConverter.target2yiri(event.text, event.message_id)
        return platform_events.FriendMessage(
            sender=platform_entities.Friend(id=event.user_id, nickname=str(event.user_id), remark=''),
            message_chain=chain,
            time=event.timestamp,
            source_platform_object=event,
        )


class ZaloAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    message_converter: ZaloMessageConverter = ZaloMessageConverter()
    event_converter: ZaloEventConverter = ZaloEventConverter()
    bot: ZaloClient

    def __init__(self, config: dict, logger: EventLogger):
        required_keys = ['app_id', 'access_token', 'secret_key', 'verify_token', 'port']
        missing = [k for k in required_keys if k not in config]
        if missing:
            raise command_errors.ParamNotEnoughError(f'Zalo 机器人缺少配置项: {missing}')

        self.bot = ZaloClient(
            app_id=config['app_id'],
            access_token=config['access_token'],
            secret_key=config['secret_key'],
            verify_token=config['verify_token'],
            logger=logger,
        )

        bot_account_id = config.get('app_id', '')
        super().__init__(bot=self.bot, bot_account_id=bot_account_id, config=config, logger=logger)

    async def reply_message(
        self,
        message_source: platform_events.FriendMessage,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        contents = await ZaloMessageConverter.yiri2target(message)
        for item in contents:
            if item.get('type') == 'text':
                await self.bot.send_message_to_one(item['content'], message_source.sender.id)

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        contents = await ZaloMessageConverter.yiri2target(message)
        for item in contents:
            if item.get('type') == 'text' and target_type == 'person':
                await self.bot.send_message_to_one(item['content'], target_id)

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        async def on_message(event: ZaloEvent):
            self.bot_account_id = self.config.get('app_id', '')
            try:
                return await callback(await self.event_converter.target2yiri(event), self)
            except Exception:
                await self.logger.error(f'Error in zalo callback: {traceback.format_exc()}')

        if event_type == platform_events.FriendMessage:
            self.bot.on_message('im')(on_message)
        elif event_type == platform_events.GroupMessage:
            pass

    async def run_async(self):
        async def shutdown_trigger_placeholder():
            while True:
                await asyncio.sleep(1)

        await self.bot.run_task(
            host=self.config.get('host', '0.0.0.0'),
            port=self.config['port'],
            shutdown_trigger=shutdown_trigger_placeholder,
        )

    async def kill(self) -> bool:
        return False

    async def unregister_listener(
        self,
        event_type: type,
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        return super().unregister_listener(event_type, callback)


