from __future__ import annotations

import asyncio
import json
import logging
import typing
from typing import Dict, Any, Optional

from ..platform import adapter
from ..platform.types import message as platform_message, events as platform_events, entities as platform_entities
from ..core import app
from ..platform.logger import EventLogger
from .rabbitmq import MessageQueueManager, RabbitMQConfig

logger = logging.getLogger(__name__)


class QueuedMessagePlatformAdapter(adapter.MessagePlatformAdapter):
    """基于消息队列的平台适配器
    
    此适配器将消息发送/接收操作转换为队列操作，
    实现分布式的消息处理架构
    """
    
    def __init__(
        self, 
        config: dict, 
        ap: app.Application, 
        logger: EventLogger,
        queue_config: RabbitMQConfig,
        platform_type: str
    ):
        super().__init__(config, ap, logger)
        self.queue_config = queue_config
        self.platform_type = platform_type
        self.queue_manager: Optional[MessageQueueManager] = None
        
        # 事件监听器存储
        self.event_listeners: Dict[type, list] = {}
        
    async def initialize_queue(self):
        """初始化消息队列连接"""
        try:
            self.queue_manager = MessageQueueManager(self.queue_config)
            await self.queue_manager.connect()
            
            # 注册消息处理器
            self.queue_manager.register_message_handler("incoming", self._handle_incoming_queue_message)
            self.queue_manager.register_message_handler("registry", self._handle_registry_queue_message)
            
            # 开始消费消息
            await self.queue_manager.start_consuming()
            
            logger.info(f"Queue-based adapter initialized for platform: {self.platform_type}")
            
        except Exception as e:
            logger.error(f"Failed to initialize message queue: {e}")
            raise
    
    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        """通过消息队列发送消息"""
        if not self.queue_manager:
            raise RuntimeError("Queue manager not initialized")
        
        # 这里我们需要确定发送给哪个客户端
        # 可以通过负载均衡算法选择一个在线的客户端
        client_id = await self._select_client_for_sending(target_type, target_id)
        
        if not client_id:
            logger.warning(f"No available client for sending message to {target_type}:{target_id}")
            return
        
        await self.queue_manager.publish_outgoing_message(
            self.platform_type,
            client_id,
            target_type,
            target_id,
            message
        )
        
        logger.debug(f"Queued outgoing message for {self.platform_type}.{client_id}")
    
    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        """通过消息队列回复消息"""
        if not self.queue_manager:
            raise RuntimeError("Queue manager not initialized")
        
        # 从消息源获取目标信息
        if isinstance(message_source, platform_events.FriendMessage):
            target_type = "person"
            target_id = message_source.sender.id
        elif isinstance(message_source, platform_events.GroupMessage):
            target_type = "group"
            target_id = message_source.group.id
        else:
            logger.warning(f"Unknown message source type: {type(message_source)}")
            return
        
        # 选择客户端发送（优先选择接收消息的同一个客户端）
        client_id = getattr(message_source, 'client_id', None)
        if not client_id:
            client_id = await self._select_client_for_sending(target_type, target_id)
        
        if not client_id:
            logger.warning(f"No available client for replying to {target_type}:{target_id}")
            return
        
        # 如果需要引用原消息，在消息链前添加Quote组件
        if quote_origin and hasattr(message_source, 'message_chain'):
            quote = platform_message.Quote(
                id=message_source.message_chain.message_id,
                origin=message_source.message_chain
            )
            message = platform_message.MessageChain([quote] + list(message))
        
        await self.queue_manager.publish_outgoing_message(
            self.platform_type,
            client_id,
            target_type,
            target_id,
            message
        )
        
        logger.debug(f"Queued reply message for {self.platform_type}.{client_id}")
    
    async def is_muted(self, group_id: int) -> bool:
        """检查是否被禁言 - 队列模式下需要查询客户端状态"""
        # 在队列模式下，这需要向客户端查询状态
        # 这里先返回False，实际实现需要客户端状态管理
        return False
    
    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[[platform_events.Event, adapter.MessagePlatformAdapter], None],
    ):
        """注册事件监听器"""
        if event_type not in self.event_listeners:
            self.event_listeners[event_type] = []
        
        self.event_listeners[event_type].append(callback)
        logger.debug(f"Registered listener for {event_type.__name__}")
    
    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[[platform_events.Event, adapter.MessagePlatformAdapter], None],
    ):
        """注销事件监听器"""
        if event_type in self.event_listeners:
            try:
                self.event_listeners[event_type].remove(callback)
                logger.debug(f"Unregistered listener for {event_type.__name__}")
            except ValueError:
                logger.warning(f"Callback not found in listeners for {event_type.__name__}")
    
    async def run_async(self):
        """异步运行"""
        await self.initialize_queue()
        
        # 保持运行状态
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Queue adapter stopping...")
            await self.kill()
    
    async def kill(self) -> bool:
        """关闭适配器"""
        if self.queue_manager:
            await self.queue_manager.disconnect()
            self.queue_manager = None
        
        logger.info(f"Queue-based adapter killed for platform: {self.platform_type}")
        return True
    
    async def _handle_incoming_queue_message(self, message_data: Dict[str, Any]):
        """处理从队列接收到的消息"""
        try:
            platform_type = message_data.get('platform_type')
            client_id = message_data.get('client_id')
            event_type = message_data.get('event_type')
            event_data = message_data.get('event_data')
            
            if platform_type != self.platform_type:
                return  # 不是当前平台的消息
            
            # 重建事件对象
            event = self._reconstruct_event(event_type, event_data, client_id)
            
            if not event:
                logger.warning(f"Failed to reconstruct event: {event_type}")
                return
            
            # 触发已注册的监听器
            event_class = type(event)
            if event_class in self.event_listeners:
                for callback in self.event_listeners[event_class]:
                    try:
                        await callback(event, self)
                    except Exception as e:
                        logger.error(f"Error in event callback: {e}")
            
            logger.debug(f"Processed incoming message from {platform_type}.{client_id}")
            
        except Exception as e:
            logger.error(f"Error handling incoming queue message: {e}")
    
    async def _handle_registry_queue_message(self, message_data: Dict[str, Any]):
        """处理客户端注册消息"""
        try:
            action = message_data.get('action')
            platform_type = message_data.get('platform_type') 
            client_id = message_data.get('client_id')
            
            if platform_type != self.platform_type:
                return  # 不是当前平台的注册消息
            
            if action == 'register':
                logger.info(f"Client registered: {platform_type}.{client_id}")
                # 这里可以更新客户端状态管理
                
            elif action == 'unregister':
                logger.info(f"Client unregistered: {platform_type}.{client_id}")
                # 这里可以清理客户端状态
                
        except Exception as e:
            logger.error(f"Error handling registry message: {e}")
    
    def _reconstruct_event(
        self, 
        event_type: str, 
        event_data: Dict[str, Any], 
        client_id: str
    ) -> Optional[platform_events.Event]:
        """从队列数据重建事件对象"""
        try:
            # 添加客户端ID到事件数据中
            event_data['client_id'] = client_id
            
            # 根据事件类型创建对应的事件对象
            if event_type == 'FriendMessage':
                return platform_events.FriendMessage.parse_obj(event_data)
            elif event_type == 'GroupMessage':
                return platform_events.GroupMessage.parse_obj(event_data)
            # 可以根据需要添加更多事件类型
            
            logger.warning(f"Unknown event type: {event_type}")
            return None
            
        except Exception as e:
            logger.error(f"Error reconstructing event {event_type}: {e}")
            return None
    
    async def _select_client_for_sending(self, target_type: str, target_id: str) -> Optional[str]:
        """选择用于发送消息的客户端
        
        这里实现简单的负载均衡逻辑，实际应用中可以根据需要实现更复杂的策略：
        - 基于客户端负载选择
        - 基于目标用户/群组的亲和性选择  
        - 基于客户端地理位置选择
        """
        # 简单实现：返回默认客户端ID
        # 实际应用中这里应该查询在线客户端列表并进行选择
        return "default_client"


class MessageQueueSerializer:
    """消息队列序列化工具"""
    
    @staticmethod
    def serialize_event(event: platform_events.Event) -> Dict[str, Any]:
        """序列化事件对象"""
        return {
            "event_type": type(event).__name__,
            "event_data": event.dict()
        }
    
    @staticmethod
    def deserialize_event(data: Dict[str, Any]) -> Optional[platform_events.Event]:
        """反序列化事件对象"""
        event_type = data.get("event_type")
        event_data = data.get("event_data")
        
        if not event_type or not event_data:
            return None
        
        try:
            # 根据事件类型创建对应的对象
            if event_type == "FriendMessage":
                return platform_events.FriendMessage.parse_obj(event_data)
            elif event_type == "GroupMessage":
                return platform_events.GroupMessage.parse_obj(event_data)
            # 添加更多事件类型支持
            
        except Exception as e:
            logger.error(f"Failed to deserialize event {event_type}: {e}")
            return None
    
    @staticmethod
    def serialize_message_chain(message_chain: platform_message.MessageChain) -> list:
        """序列化消息链"""
        return [msg.dict() for msg in message_chain]
    
    @staticmethod
    def deserialize_message_chain(data: list) -> platform_message.MessageChain:
        """反序列化消息链"""
        try:
            return platform_message.MessageChain.parse_obj(data)
        except Exception as e:
            logger.error(f"Failed to deserialize message chain: {e}")
            return platform_message.MessageChain([])