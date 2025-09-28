from __future__ import annotations

import asyncio
import aiohttp
import hashlib
import hmac
import json
import traceback
import typing
from datetime import datetime

import pydantic
import quart

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message


class FacebookMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain) -> list[dict[str, typing.Any]]:
        components: list[dict[str, typing.Any]] = []

        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                if component.text:
                    components.append({'type': 'text', 'text': component.text})
            elif isinstance(component, platform_message.Image):
                image_url = ''
                if component.url:
                    image_url = component.url
                elif component.base64:
                    # Messenger 发送 API 暂不直接支持 base64 图片，跳过以避免报错
                    continue
                elif component.path:
                    continue

                if image_url:
                    components.append(
                        {
                            'type': 'attachment',
                            'attachment': {
                                'type': 'image',
                                'payload': {
                                    'url': image_url,
                                    'is_reusable': True,
                                },
                            },
                        }
                    )

        return components

    @staticmethod
    async def target2yiri(event: dict[str, typing.Any]) -> platform_message.MessageChain:
        components: list[platform_message.MessageComponent] = []

        timestamp = event.get('timestamp')
        msg = event.get('message', {})
        mid = msg.get('mid', '')
        if timestamp:
            message_time = datetime.fromtimestamp(timestamp / 1000)
            components.append(platform_message.Source(id=mid or timestamp, time=message_time))

        if 'text' in msg:
            components.append(platform_message.Plain(text=msg['text']))

        for attachment in msg.get('attachments', []) or []:
            att_type = attachment.get('type')
            payload = attachment.get('payload', {})
            if att_type == 'image' and payload.get('url'):
                components.append(platform_message.Image(url=payload['url']))
            else:
                components.append(
                    platform_message.Unknown(
                        text=f"Unsupported attachment type: {att_type or 'unknown'}"
                    )
                )

        return platform_message.MessageChain(components)


class FacebookEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent) -> dict[str, typing.Any]:
        return event.source_platform_object

    @staticmethod
    async def target2yiri(event: dict[str, typing.Any], bot_account_id: str) -> platform_events.Event:
        message_chain = await FacebookMessageConverter.target2yiri(event)

        sender_id = event.get('sender', {}).get('id', '')
        timestamp = event.get('timestamp', 0)

        return platform_events.FriendMessage(
            sender=platform_entities.Friend(
                id=sender_id,
                nickname=sender_id,
                remark='',
            ),
            message_chain=message_chain,
            time=timestamp / 1000 if timestamp else 0,
            source_platform_object=event,
        )


class FacebookAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    quart_app: quart.Quart = pydantic.Field(exclude=True)
    message_converter: FacebookMessageConverter = FacebookMessageConverter()
    event_converter: FacebookEventConverter = FacebookEventConverter()

    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ]

    page_access_token: str
    verify_token: str
    app_secret: str
    graph_version: str
    webhook_path: str

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        quart_app = quart.Quart(__name__)

        super().__init__(
            config=config,
            logger=logger,
            quart_app=quart_app,
            bot_account_id=config.get('page_id', ''),
            listeners={},
            page_access_token=config['page_access_token'],
            verify_token=config['verify_token'],
            app_secret=config.get('app_secret', ''),
            graph_version=config.get('graph_version', 'v17.0'),
            webhook_path=config.get('webhook_path', '/facebook/webhook'),
        )

        @self.quart_app.route(self.webhook_path, methods=['GET'])
        async def facebook_verify():
            mode = quart.request.args.get('hub.mode')
            token = quart.request.args.get('hub.verify_token')
            challenge = quart.request.args.get('hub.challenge', '')

            if mode == 'subscribe' and token == self.verify_token:
                return quart.Response(challenge, status=200)

            return quart.Response('Forbidden', status=403)

        @self.quart_app.route(self.webhook_path, methods=['POST'])
        async def facebook_webhook():
            try:
                raw_body = await quart.request.get_data()

                if self.app_secret:
                    signature = quart.request.headers.get('X-Hub-Signature-256', '')
                    if not self._verify_signature(signature, raw_body):
                        await self.logger.warning('Facebook webhook signature verification failed')
                        return quart.Response('Invalid signature', status=403)

                data = json.loads(raw_body.decode('utf-8') or '{}')

                await self._dispatch_events(data)

                return quart.Response('OK', status=200)
            except Exception:
                await self.logger.error(f'Error in Facebook callback: {traceback.format_exc()}')
                return quart.Response('Internal Error', status=500)

    async def _dispatch_events(self, payload: dict[str, typing.Any]):
        if payload.get('object') != 'page':
            return

        for entry in payload.get('entry', []):
            for messaging_event in entry.get('messaging', []):
                if messaging_event.get('message') is None:
                    continue

                if messaging_event.get('message', {}).get('is_echo'):
                    continue

                try:
                    lb_event = await self.event_converter.target2yiri(messaging_event, self.bot_account_id)
                    listener = self.listeners.get(lb_event.__class__)
                    if listener:
                        await listener(lb_event, self)
                except Exception:
                    await self.logger.error(f'Error while handling Facebook event: {traceback.format_exc()}')

    def _verify_signature(self, signature: str, raw_body: bytes) -> bool:
        if not signature.startswith('sha256='):
            return False

        expected = hmac.new(self.app_secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()

        return hmac.compare_digest(signature.split('=')[1], expected)

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        components = await FacebookMessageConverter.yiri2target(message)

        for component in components:
            await self._send_component(target_id, component)

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        source_event = typing.cast(dict[str, typing.Any], message_source.source_platform_object)
        recipient_id = source_event.get('sender', {}).get('id')

        if not recipient_id:
            await self.logger.warning('Facebook reply skipped: missing sender id')
            return

        components = await FacebookMessageConverter.yiri2target(message)

        for component in components:
            await self._send_component(recipient_id, component)

    async def _send_component(self, recipient_id: str, component: dict[str, typing.Any]):
        payload = {
            'recipient': {'id': recipient_id},
            'messaging_type': 'RESPONSE',
        }

        if component['type'] == 'text':
            payload['message'] = {'text': component['text']}
        elif component['type'] == 'attachment':
            payload['message'] = {'attachment': component['attachment']}
        else:
            return

        await self._call_send_api(payload)

    async def _call_send_api(self, payload: dict[str, typing.Any]):
        url = f'https://graph.facebook.com/{self.graph_version}/me/messages'

        async with aiohttp.ClientSession() as session:
            async with session.post(url, params={'access_token': self.page_access_token}, json=payload) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    await self.logger.error(f'Facebook send API failed: {resp.status} {text}')

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter],
            None,
        ],
    ):
        self.listeners[event_type] = callback

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter],
            None,
        ],
    ):
        self.listeners.pop(event_type, None)

    async def run_async(self):
        host = self.config.get('host', '0.0.0.0')
        port = self.config.get('port', 5010)

        async def shutdown_trigger_placeholder():
            while True:
                await asyncio.sleep(1)

        await self.quart_app.run_task(
            host=host,
            port=port,
            shutdown_trigger=shutdown_trigger_placeholder,
        )

    async def kill(self) -> bool:
        return False

    async def is_stream_output_supported(self) -> bool:
        return bool(self.config.get('enable-stream-reply'))

