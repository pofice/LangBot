from __future__ import annotations

import asyncio
import json
import logging
import typing
import uuid
from typing import Dict, Any, Optional

from ..platform import adapter  
from ..platform.types import message as platform_message, events as platform_events
from ..core import app
from ..platform.logger import EventLogger
from .rabbitmq import MessageQueueClient, RabbitMQConfig

logger = logging.getLogger(__name__)


class ClientQueueAdapter:
    """客户端消息队列适配器
    
    用于微信机器人客户端，将本地消息收发转换为队列操作
    """
    
    def __init__(
        self,
        platform_type: str,
        client_id: str,
        queue_config: RabbitMQConfig,
        original_adapter: adapter.MessagePlatformAdapter
    ):
        self.platform_type = platform_type
        self.client_id = client_id or self._generate_client_id()
        self.queue_config = queue_config
        self.original_adapter = original_adapter
        
        self.queue_client: Optional[MessageQueueClient] = None
        self.is_running = False
        
    def _generate_client_id(self) -> str:
        """生成唯一的客户端ID"""
        return f"client_{uuid.uuid4().hex[:8]}"
    
    async def initialize(self):
        """初始化队列客户端"""
        try:
            self.queue_client = MessageQueueClient(
                self.queue_config,
                self.platform_type,
                self.client_id
            )
            
            await self.queue_client.connect()
            
            # 设置出站消息处理器
            self.queue_client.set_outgoing_message_handler(self._handle_outgoing_message)
            
            # 开始消费出站消息
            await self.queue_client.start_consuming_outgoing()
            
            # 注册客户端
            await self._register_client()
            
            logger.info(f"Client queue adapter initialized: {self.platform_type}.{self.client_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize client queue adapter: {e}")
            raise
    
    async def start(self):
        """启动适配器"""
        await self.initialize()
        
        # 包装原始适配器的事件监听器，转发到队列
        self._wrap_original_adapter()
        
        # 启动原始适配器
        self.is_running = True
        
        # 启动心跳任务
        asyncio.create_task(self._heartbeat_task())
        
        # 运行原始适配器
        await self.original_adapter.run_async()
    
    async def stop(self):
        """停止适配器"""
        self.is_running = False
        
        # 注销客户端
        if self.queue_client:
            await self._unregister_client()
            await self.queue_client.disconnect()
        
        # 停止原始适配器
        await self.original_adapter.kill()
        
        logger.info(f"Client queue adapter stopped: {self.platform_type}.{self.client_id}")
    
    def _wrap_original_adapter(self):
        """包装原始适配器的方法，转发消息到队列"""
        
        # 保存原始的register_listener方法
        original_register_listener = self.original_adapter.register_listener
        
        def wrapped_register_listener(event_type, callback):
            """包装的事件监听器注册方法"""
            
            async def queue_callback(event, adapter):
                """转发到队列的回调函数"""
                try:
                    # 先发送到队列
                    if self.queue_client:
                        await self.queue_client.send_incoming_message(event)
                    
                    # 然后调用原始回调（用于本地处理，如果需要的话）
                    # await callback(event, adapter)
                    
                except Exception as e:
                    logger.error(f"Error in queue callback: {e}")
            
            # 注册包装后的回调
            original_register_listener(event_type, queue_callback)
        
        # 替换原始方法
        self.original_adapter.register_listener = wrapped_register_listener
        
        # 包装send_message方法（如果客户端需要本地发送的话）
        original_send_message = self.original_adapter.send_message
        
        async def wrapped_send_message(target_type: str, target_id: str, message: platform_message.MessageChain):
            """包装的发送消息方法"""
            # 在队列模式下，发送消息应该通过队列，但这里保持原始行为以支持混合模式
            return await original_send_message(target_type, target_id, message)
        
        self.original_adapter.send_message = wrapped_send_message
    
    async def _handle_outgoing_message(self, message_data: Dict[str, Any]):
        """处理从队列接收到的出站消息"""
        try:
            platform_type = message_data.get('platform_type')
            client_id = message_data.get('client_id')
            
            # 检查是否是发给当前客户端的消息
            if platform_type != self.platform_type or client_id != self.client_id:
                return
            
            target_type = message_data.get('target_type')
            target_id = message_data.get('target_id')
            message_data_list = message_data.get('message_data', [])
            
            # 重建消息链
            message_chain = platform_message.MessageChain.parse_obj(message_data_list)
            
            # 使用原始适配器发送消息
            await self.original_adapter.send_message(target_type, target_id, message_chain)
            
            logger.debug(f"Sent message via original adapter: {target_type}:{target_id}")
            
        except Exception as e:
            logger.error(f"Error handling outgoing message: {e}")
    
    async def _register_client(self):
        """注册客户端到队列"""
        if not self.queue_client:
            return
        
        client_info = {
            "client_id": self.client_id,
            "platform_type": self.platform_type,
            "status": "online",
            "config": self.original_adapter.config
        }
        
        # 通过队列管理器发送注册消息（这里需要直接使用底层连接）
        if hasattr(self.queue_client, 'message_exchange'):
            routing_key = f"registry.{self.platform_type}"
            
            message_body = {
                "action": "register",
                "timestamp": asyncio.get_event_loop().time(),
                "platform_type": self.platform_type,
                "client_id": self.client_id,
                "client_info": client_info
            }
            
            from aio_pika import Message, DeliveryMode
            
            message = Message(
                json.dumps(message_body, ensure_ascii=False).encode("utf-8"),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json"
            )
            
            await self.queue_client.message_exchange.publish(
                message,
                routing_key=routing_key
            )
            
            logger.info(f"Registered client in queue: {self.platform_type}.{self.client_id}")
    
    async def _unregister_client(self):
        """注销客户端"""
        if not self.queue_client:
            return
        
        if hasattr(self.queue_client, 'message_exchange'):
            routing_key = f"registry.{self.platform_type}"
            
            message_body = {
                "action": "unregister",
                "timestamp": asyncio.get_event_loop().time(),
                "platform_type": self.platform_type,
                "client_id": self.client_id
            }
            
            from aio_pika import Message, DeliveryMode
            
            message = Message(
                json.dumps(message_body, ensure_ascii=False).encode("utf-8"),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json"
            )
            
            await self.queue_client.message_exchange.publish(
                message,
                routing_key=routing_key
            )
            
            logger.info(f"Unregistered client from queue: {self.platform_type}.{self.client_id}")
    
    async def _heartbeat_task(self):
        """心跳任务，定期发送客户端状态"""
        while self.is_running:
            try:
                await asyncio.sleep(30)  # 每30秒发送一次心跳
                
                if self.queue_client and hasattr(self.queue_client, 'message_exchange'):
                    routing_key = f"registry.{self.platform_type}"
                    
                    message_body = {
                        "action": "heartbeat",
                        "timestamp": asyncio.get_event_loop().time(),
                        "platform_type": self.platform_type,
                        "client_id": self.client_id,
                        "status": "online"
                    }
                    
                    from aio_pika import Message, DeliveryMode
                    
                    message = Message(
                        json.dumps(message_body, ensure_ascii=False).encode("utf-8"),
                        delivery_mode=DeliveryMode.PERSISTENT,
                        content_type="application/json"
                    )
                    
                    await self.queue_client.message_exchange.publish(
                        message,
                        routing_key=routing_key
                    )
                    
                    logger.debug(f"Sent heartbeat: {self.platform_type}.{self.client_id}")
                    
            except Exception as e:
                logger.error(f"Error in heartbeat task: {e}")
                break


async def create_queued_wechat_adapter(
    config: dict,
    ap: app.Application,
    logger: EventLogger,
    queue_config: RabbitMQConfig,
    client_id: Optional[str] = None
) -> ClientQueueAdapter:
    """创建基于队列的微信适配器"""
    
    # 导入原始的微信适配器
    from ..platform.sources.wecom import WecomAdapter
    
    # 创建原始适配器实例
    original_adapter = WecomAdapter(config, ap, logger)
    
    # 创建队列适配器
    client_adapter = ClientQueueAdapter(
        platform_type="wecom",
        client_id=client_id,
        queue_config=queue_config,
        original_adapter=original_adapter
    )
    
    return client_adapter