#!/usr/bin/env python3
"""
RabbitMQ队列模式使用示例

此示例展示如何使用RabbitMQ队列实现分布式的微信机器人架构：
- 服务端：LangBot核心，处理AI推理和业务逻辑
- 客户端：微信机器人客户端，处理微信消息收发

使用场景：
1. 多个微信客户端分布在不同机器上
2. 统一的LangBot核心处理所有消息
3. 高可用和负载均衡
"""

import asyncio
import logging
from pkg.messaging.rabbitmq import RabbitMQConfig
from pkg.messaging.queue_adapter import QueuedMessagePlatformAdapter
from pkg.messaging.client_adapter import create_queued_wechat_adapter

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_server_mode():
    """运行服务端模式 - LangBot核心"""
    
    # RabbitMQ配置
    queue_config = RabbitMQConfig(
        host="localhost",
        port=5672,
        username="guest",
        password="guest"
    )
    
    # 创建队列适配器
    from pkg.core import app
    from pkg.platform.logger import EventLogger
    
    # 这里需要根据实际应用初始化
    ap = None  # app.Application实例
    event_logger = EventLogger("queue_server")
    
    adapter = QueuedMessagePlatformAdapter(
        config={},
        ap=ap,
        logger=event_logger,
        queue_config=queue_config,
        platform_type="wecom"
    )
    
    # 注册事件监听器
    from pkg.platform.types import events as platform_events
    
    async def handle_friend_message(event, adapter):
        """处理好友消息"""
        logger.info(f"Received friend message: {event.message_chain}")
        
        # 这里添加AI处理逻辑
        # response = await ai_process(event.message_chain)
        
        # 回复消息
        from pkg.platform.types.message import MessageChain, Plain
        response_message = MessageChain([Plain("收到消息，正在处理...")])
        
        await adapter.reply_message(event, response_message)
    
    async def handle_group_message(event, adapter):
        """处理群组消息"""
        logger.info(f"Received group message: {event.message_chain}")
        # 群组消息处理逻辑
    
    # 注册监听器
    adapter.register_listener(platform_events.FriendMessage, handle_friend_message)
    adapter.register_listener(platform_events.GroupMessage, handle_group_message)
    
    # 运行适配器
    await adapter.run_async()


async def run_client_mode():
    """运行客户端模式 - 微信机器人客户端"""
    
    # RabbitMQ配置
    queue_config = RabbitMQConfig(
        host="localhost",  # RabbitMQ服务器地址
        port=5672,
        username="guest",
        password="guest"
    )
    
    # 微信客户端配置
    wecom_config = {
        'corpid': 'your_corp_id',
        'secret': 'your_secret',
        'token': 'your_token',
        'EncodingAESKey': 'your_encoding_aes_key',
        'contacts_secret': 'your_contacts_secret',
        'host': '0.0.0.0',
        'port': 8080
    }
    
    # 创建队列化的微信适配器
    from pkg.core import app
    from pkg.platform.logger import EventLogger
    
    # 这里需要根据实际应用初始化
    ap = None  # app.Application实例
    event_logger = EventLogger("queue_client")
    
    client_adapter = await create_queued_wechat_adapter(
        config=wecom_config,
        ap=ap,
        logger=event_logger,
        queue_config=queue_config,
        client_id="wecom_client_001"  # 可选，会自动生成
    )
    
    # 启动客户端适配器
    await client_adapter.start()


async def main():
    """主函数"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python example.py [server|client]")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == "server":
        print("Starting server mode (LangBot core)...")
        await run_server_mode()
    elif mode == "client":
        print("Starting client mode (WeChat bot client)...")
        await run_client_mode()
    else:
        print("Invalid mode. Use 'server' or 'client'")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)