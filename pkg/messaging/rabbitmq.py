import asyncio
import json
import logging
import typing
from datetime import datetime
from typing import Optional, Dict, Any, Callable

import aio_pika
from aio_pika import Exchange, Queue, Message, DeliveryMode
from aio_pika.abc import AbstractConnection, AbstractChannel

from ..platform.types import message as platform_message, events as platform_events

logger = logging.getLogger(__name__)


class RabbitMQConfig:
    """RabbitMQ配置类"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5672,
        username: str = "guest", 
        password: str = "guest",
        virtual_host: str = "/",
        connection_timeout: int = 30,
        heartbeat: int = 60
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.virtual_host = virtual_host
        self.connection_timeout = connection_timeout
        self.heartbeat = heartbeat
    
    @property
    def url(self) -> str:
        """构建RabbitMQ连接URL"""
        return f"amqp://{self.username}:{self.password}@{self.host}:{self.port}{self.virtual_host}"


class MessageQueueManager:
    """消息队列管理器"""
    
    def __init__(self, config: RabbitMQConfig):
        self.config = config
        self.connection: Optional[AbstractConnection] = None
        self.channel: Optional[AbstractChannel] = None
        
        # 交换机和队列
        self.message_exchange: Optional[Exchange] = None
        self.incoming_queue: Optional[Queue] = None
        self.outgoing_queue: Optional[Queue] = None
        self.client_registry_queue: Optional[Queue] = None
        
        # 回调函数
        self.message_handlers: Dict[str, Callable] = {}
        
    async def connect(self):
        """连接到RabbitMQ"""
        try:
            self.connection = await aio_pika.connect_robust(
                self.config.url,
                timeout=self.config.connection_timeout,
                heartbeat=self.config.heartbeat
            )
            
            self.channel = await self.connection.channel()
            
            # 设置QoS - 每次只处理一个消息
            await self.channel.set_qos(prefetch_count=1)
            
            await self._setup_exchanges_and_queues()
            
            logger.info("Successfully connected to RabbitMQ")
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    async def disconnect(self):
        """断开RabbitMQ连接"""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            logger.info("Disconnected from RabbitMQ")
    
    async def _setup_exchanges_and_queues(self):
        """设置交换机和队列"""
        # 创建消息交换机 - 使用topic类型支持路由
        self.message_exchange = await self.channel.declare_exchange(
            "langbot_messages", 
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
        # 创建队列
        self.incoming_queue = await self.channel.declare_queue(
            "incoming_messages",
            durable=True,
            arguments={"x-message-ttl": 300000}  # 5分钟TTL
        )
        
        self.outgoing_queue = await self.channel.declare_queue(
            "outgoing_messages", 
            durable=True,
            arguments={"x-message-ttl": 300000}
        )
        
        self.client_registry_queue = await self.channel.declare_queue(
            "client_registry",
            durable=True
        )
        
        # 绑定队列到交换机
        await self.incoming_queue.bind(
            self.message_exchange, 
            routing_key="incoming.*.*"
        )
        
        await self.outgoing_queue.bind(
            self.message_exchange,
            routing_key="outgoing.*.*"  
        )
        
        await self.client_registry_queue.bind(
            self.message_exchange,
            routing_key="registry.*"
        )
    
    async def publish_incoming_message(
        self, 
        platform_type: str,
        client_id: str, 
        event: platform_events.Event
    ):
        """发布接收到的消息到队列"""
        routing_key = f"incoming.{platform_type}.{client_id}"
        
        message_body = {
            "timestamp": datetime.now().isoformat(),
            "platform_type": platform_type,
            "client_id": client_id,
            "event_type": type(event).__name__,
            "event_data": event.dict()
        }
        
        message = Message(
            json.dumps(message_body, ensure_ascii=False).encode("utf-8"),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json"
        )
        
        await self.message_exchange.publish(
            message,
            routing_key=routing_key
        )
        
        logger.debug(f"Published incoming message: {routing_key}")
    
    async def publish_outgoing_message(
        self,
        platform_type: str, 
        client_id: str,
        target_type: str,
        target_id: str,
        message_chain: platform_message.MessageChain
    ):
        """发布要发送的消息到队列"""
        routing_key = f"outgoing.{platform_type}.{client_id}"
        
        message_body = {
            "timestamp": datetime.now().isoformat(),
            "platform_type": platform_type,
            "client_id": client_id,
            "target_type": target_type,
            "target_id": target_id,
            "message_data": [msg.dict() for msg in message_chain]
        }
        
        message = Message(
            json.dumps(message_body, ensure_ascii=False).encode("utf-8"),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json"
        )
        
        await self.message_exchange.publish(
            message,
            routing_key=routing_key
        )
        
        logger.debug(f"Published outgoing message: {routing_key}")
    
    async def register_client(
        self,
        platform_type: str,
        client_id: str, 
        client_info: Dict[str, Any]
    ):
        """注册客户端"""
        routing_key = f"registry.{platform_type}"
        
        message_body = {
            "action": "register",
            "timestamp": datetime.now().isoformat(),
            "platform_type": platform_type,
            "client_id": client_id,
            "client_info": client_info
        }
        
        message = Message(
            json.dumps(message_body, ensure_ascii=False).encode("utf-8"),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json"
        )
        
        await self.message_exchange.publish(
            message,
            routing_key=routing_key
        )
        
        logger.info(f"Registered client: {platform_type}.{client_id}")
    
    async def unregister_client(
        self,
        platform_type: str,
        client_id: str
    ):
        """注销客户端"""
        routing_key = f"registry.{platform_type}"
        
        message_body = {
            "action": "unregister", 
            "timestamp": datetime.now().isoformat(),
            "platform_type": platform_type,
            "client_id": client_id
        }
        
        message = Message(
            json.dumps(message_body, ensure_ascii=False).encode("utf-8"),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json"
        )
        
        await self.message_exchange.publish(
            message,
            routing_key=routing_key
        )
        
        logger.info(f"Unregistered client: {platform_type}.{client_id}")
    
    def register_message_handler(
        self,
        message_type: str,
        handler: Callable[[Dict[str, Any]], typing.Awaitable[None]]
    ):
        """注册消息处理器"""
        self.message_handlers[message_type] = handler
    
    async def start_consuming(self):
        """开始消费消息"""
        if not self.incoming_queue or not self.client_registry_queue:
            raise RuntimeError("Queues not initialized")
        
        # 消费接收消息队列
        await self.incoming_queue.consume(self._handle_incoming_message)
        
        # 消费客户端注册队列  
        await self.client_registry_queue.consume(self._handle_registry_message)
        
        logger.info("Started consuming messages from queues")
    
    async def _handle_incoming_message(self, message: aio_pika.IncomingMessage):
        """处理接收到的消息"""
        try:
            async with message.process():
                body = json.loads(message.body.decode("utf-8"))
                
                # 调用注册的处理器
                handler = self.message_handlers.get("incoming")
                if handler:
                    await handler(body)
                else:
                    logger.warning("No handler registered for incoming messages")
                    
        except Exception as e:
            logger.error(f"Error processing incoming message: {e}")
    
    async def _handle_registry_message(self, message: aio_pika.IncomingMessage):
        """处理客户端注册消息"""
        try:
            async with message.process():
                body = json.loads(message.body.decode("utf-8"))
                
                # 调用注册的处理器
                handler = self.message_handlers.get("registry")
                if handler:
                    await handler(body)
                else:
                    logger.warning("No handler registered for registry messages")
                    
        except Exception as e:
            logger.error(f"Error processing registry message: {e}")


class MessageQueueClient:
    """消息队列客户端 - 供机器人客户端使用"""
    
    def __init__(self, config: RabbitMQConfig, platform_type: str, client_id: str):
        self.config = config
        self.platform_type = platform_type
        self.client_id = client_id
        self.connection: Optional[AbstractConnection] = None
        self.channel: Optional[AbstractChannel] = None
        self.message_exchange: Optional[Exchange] = None
        self.outgoing_queue: Optional[Queue] = None
        
        # 消息处理器
        self.outgoing_message_handler: Optional[Callable] = None
        
    async def connect(self):
        """连接到RabbitMQ"""
        try:
            self.connection = await aio_pika.connect_robust(
                self.config.url,
                timeout=self.config.connection_timeout,
                heartbeat=self.config.heartbeat
            )
            
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=1)
            
            # 获取交换机
            self.message_exchange = await self.channel.declare_exchange(
                "langbot_messages",
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            
            # 创建客户端专用的出站消息队列
            queue_name = f"outgoing_{self.platform_type}_{self.client_id}"
            self.outgoing_queue = await self.channel.declare_queue(
                queue_name,
                durable=True,
                auto_delete=True,  # 客户端断开时自动删除
                arguments={"x-message-ttl": 300000}
            )
            
            # 绑定到指定的路由键
            routing_key = f"outgoing.{self.platform_type}.{self.client_id}"
            await self.outgoing_queue.bind(
                self.message_exchange,
                routing_key=routing_key
            )
            
            logger.info(f"Message queue client connected: {self.platform_type}.{self.client_id}")
            
        except Exception as e:
            logger.error(f"Failed to connect message queue client: {e}")
            raise
    
    async def disconnect(self):
        """断开连接"""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            logger.info(f"Message queue client disconnected: {self.platform_type}.{self.client_id}")
    
    async def send_incoming_message(self, event: platform_events.Event):
        """发送接收到的消息"""
        routing_key = f"incoming.{self.platform_type}.{self.client_id}"
        
        message_body = {
            "timestamp": datetime.now().isoformat(),
            "platform_type": self.platform_type,
            "client_id": self.client_id,
            "event_type": type(event).__name__,
            "event_data": event.dict()
        }
        
        message = Message(
            json.dumps(message_body, ensure_ascii=False).encode("utf-8"),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json"
        )
        
        await self.message_exchange.publish(
            message,
            routing_key=routing_key
        )
        
        logger.debug(f"Sent incoming message: {routing_key}")
    
    def set_outgoing_message_handler(
        self,
        handler: Callable[[Dict[str, Any]], typing.Awaitable[None]]
    ):
        """设置出站消息处理器"""
        self.outgoing_message_handler = handler
    
    async def start_consuming_outgoing(self):
        """开始消费出站消息"""
        if not self.outgoing_queue:
            raise RuntimeError("Outgoing queue not initialized")
        
        await self.outgoing_queue.consume(self._handle_outgoing_message)
        logger.info(f"Started consuming outgoing messages: {self.platform_type}.{self.client_id}")
    
    async def _handle_outgoing_message(self, message: aio_pika.IncomingMessage):
        """处理出站消息"""
        try:
            async with message.process():
                body = json.loads(message.body.decode("utf-8"))
                
                if self.outgoing_message_handler:
                    await self.outgoing_message_handler(body)
                else:
                    logger.warning("No outgoing message handler set")
                    
        except Exception as e:
            logger.error(f"Error processing outgoing message: {e}")