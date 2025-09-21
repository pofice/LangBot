from __future__ import annotations

import asyncio
import hmac
import hashlib
import json
import typing

from quart import Quart, request, Response
import aiohttp

from .zaloevent import ZaloEvent


class ZaloClient:
    def __init__(self, app_id: str, access_token: str, secret_key: str, verify_token: str, logger):
        self.app_id = app_id
        self.access_token = access_token
        self.secret_key = secret_key.encode('utf-8')
        self.verify_token = verify_token
        self.logger = logger

        self._app = Quart(__name__)
        self._message_handlers: dict[str, typing.Callable[[ZaloEvent], typing.Awaitable[None]]] = {}

        @_self_route(self._app, '/zalo/webhook', methods=['GET'])
        async def verify_route():
            token = request.args.get('verify_token', '')
            if token == self.verify_token:
                return Response('OK', status=200)
            return Response('Forbidden', status=403)

        @_self_route(self._app, '/zalo/webhook', methods=['POST'])
        async def event_route():
            raw_body = await request.get_data()  # bytes
            signature = request.headers.get('X-Zalo-Signature', '')
            if not self._verify_signature(raw_body, signature):
                await self.logger.error('Zalo signature verify failed')
                return Response('Forbidden', status=403)

            try:
                payload = json.loads(raw_body.decode('utf-8'))
            except Exception:
                await self.logger.error('Zalo payload parse failed')
                return Response('Bad Request', status=400)

            event = self._parse_event(payload)
            if event and event.type in self._message_handlers:
                await self._message_handlers[event.type](event)
            return Response('OK', status=200)

    def on_message(self, kind: str):
        def decorator(func: typing.Callable[[ZaloEvent], typing.Awaitable[None]]):
            self._message_handlers[kind] = func
            return func
        return decorator

    async def run_task(self, host: str, port: int, shutdown_trigger: typing.Callable[[], typing.Awaitable[None]]):
        async def _serve():
            await self._app.run_task(host=host, port=port)

        await asyncio.gather(_serve(), shutdown_trigger())

    def _verify_signature(self, raw_body: bytes, signature: str) -> bool:
        if not signature:
            return False
        # NOTE: 具体签名算法以 Zalo 文档为准，此处使用 HMAC-SHA256 占位
        mac = hmac.new(self.secret_key, raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(mac, signature)

    def _parse_event(self, payload: dict) -> ZaloEvent | None:
        # 依据 Zalo Webhook 结构提取文本消息；保持最小可用
        try:
            # 以下字段名需按官方文档调整
            message = payload.get('message', {})
            text = message.get('text')
            user_id = payload.get('sender', {}).get('id')
            message_id = message.get('msg_id') or payload.get('message_id') or ''
            if text and user_id:
                return ZaloEvent(
                    type='im',
                    user_id=str(user_id),
                    text=str(text),
                    message_id=str(message_id),
                    timestamp=ZaloEvent.now_ts(),
                )
        except Exception:
            pass
        return None

    async def send_message_to_one(self, content: str, user_id: str):
        # 依据 Zalo 发送 API（URL/参数需按官方文档调整）
        url = 'https://openapi.zalo.me/v3.0/oa/message'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.access_token}',
        }
        data = {
            'recipient': { 'user_id': user_id },
            'message': { 'text': content },
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=json.dumps(data)) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    await self.logger.error(f'Zalo send failed: {resp.status} {text}')


def _self_route(app: Quart, rule: str, methods: list[str]):
    def wrapper(func):
        app.add_url_rule(rule, view_func=func, methods=methods)
        return func
    return wrapper


