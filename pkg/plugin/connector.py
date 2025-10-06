# For connect to plugin runtime.
from __future__ import annotations

import asyncio
from typing import Any
import typing
import os
import sys

from async_lru import alru_cache

from ..core import app
from . import handler
from ..utils import platform
from langbot_plugin.runtime.io.controllers.stdio import client as stdio_client_controller
from langbot_plugin.runtime.io.controllers.ws import client as ws_client_controller
from langbot_plugin.api.entities import events
from langbot_plugin.api.entities import context
import langbot_plugin.runtime.io.connection as base_connection
from langbot_plugin.api.definition.components.manifest import ComponentManifest
from langbot_plugin.api.entities.builtin.command import context as command_context
from langbot_plugin.runtime.plugin.mgr import PluginInstallSource
from ..core import taskmgr


class PluginRuntimeConnector:
    """Plugin runtime connector"""

    ap: app.Application

    handler: handler.RuntimeConnectionHandler

    handler_task: asyncio.Task

    heartbeat_task: asyncio.Task | None = None

    stdio_client_controller: stdio_client_controller.StdioClientController

    ctrl: stdio_client_controller.StdioClientController | ws_client_controller.WebSocketClientController

    runtime_disconnect_callback: typing.Callable[
        [PluginRuntimeConnector], typing.Coroutine[typing.Any, typing.Any, None]
    ]

    is_enable_plugin: bool = True
    """Mark if the plugin system is enabled"""

    def __init__(
        self,
        ap: app.Application,
        runtime_disconnect_callback: typing.Callable[
            [PluginRuntimeConnector], typing.Coroutine[typing.Any, typing.Any, None]
        ],
    ):
        self.ap = ap
        self.runtime_disconnect_callback = runtime_disconnect_callback
        self.is_enable_plugin = self.ap.instance_config.data.get('plugin', {}).get('enable', True)

    async def heartbeat_loop(self):
        while True:
            await asyncio.sleep(10)
            try:
                await self.ping_plugin_runtime()
                self.ap.logger.debug('Heartbeat to plugin runtime success.')
            except Exception as e:
                self.ap.logger.debug(f'Failed to heartbeat to plugin runtime: {e}')

    async def initialize(self):
        if not self.is_enable_plugin:
            self.ap.logger.info('Plugin system is disabled.')
            return

        async def new_connection_callback(connection: base_connection.Connection):
            async def disconnect_callback(rchandler: handler.RuntimeConnectionHandler) -> bool:
                if platform.get_platform() == 'docker' or platform.use_websocket_to_connect_plugin_runtime():
                    self.ap.logger.error('Disconnected from plugin runtime, trying to reconnect...')
                    await self.runtime_disconnect_callback(self)
                    return False
                else:
                    self.ap.logger.error(
                        'Disconnected from plugin runtime, cannot automatically reconnect while LangBot connects to plugin runtime via stdio, please restart LangBot.'
                    )
                    return False

            self.handler = handler.RuntimeConnectionHandler(connection, disconnect_callback, self.ap)

            self.handler_task = asyncio.create_task(self.handler.run())
            _ = await self.handler.ping()
            self.ap.logger.info('Connected to plugin runtime.')
            await self.handler_task

        task: asyncio.Task | None = None

        if platform.get_platform() == 'docker' or platform.use_websocket_to_connect_plugin_runtime():  # use websocket
            self.ap.logger.info('use websocket to connect to plugin runtime')
            ws_url = self.ap.instance_config.data.get('plugin', {}).get(
                'runtime_ws_url', 'ws://langbot_plugin_runtime:5400/control/ws'
            )

            async def make_connection_failed_callback(
                ctrl: ws_client_controller.WebSocketClientController, exc: Exception = None
            ) -> None:
                if exc is not None:
                    self.ap.logger.error(f'Failed to connect to plugin runtime({ws_url}): {exc}')
                else:
                    self.ap.logger.error(f'Failed to connect to plugin runtime({ws_url}), trying to reconnect...')
                await self.runtime_disconnect_callback(self)

            self.ctrl = ws_client_controller.WebSocketClientController(
                ws_url=ws_url,
                make_connection_failed_callback=make_connection_failed_callback,
            )
            task = self.ctrl.run(new_connection_callback)
        else:  # stdio
            self.ap.logger.info('use stdio to connect to plugin runtime')
            # cmd: lbp rt -s
            python_path = sys.executable
            env = os.environ.copy()
            self.ctrl = stdio_client_controller.StdioClientController(
                command=python_path,
                args=['-m', 'langbot_plugin.cli.__init__', 'rt', '-s'],
                env=env,
            )
            task = self.ctrl.run(new_connection_callback)

        if self.heartbeat_task is None:
            self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())

        asyncio.create_task(task)

    async def initialize_plugins(self):
        pass

    async def ping_plugin_runtime(self):
        if not hasattr(self, 'handler'):
            raise Exception('Plugin runtime is not connected')

        return await self.handler.ping()

    async def install_plugin(
        self,
        install_source: PluginInstallSource,
        install_info: dict[str, Any],
        task_context: taskmgr.TaskContext | None = None,
    ):
        if install_source == PluginInstallSource.LOCAL:
            # transfer file before install
            file_bytes = install_info['plugin_file']
            file_key = await self.handler.send_file(file_bytes, 'lbpkg')
            install_info['plugin_file_key'] = file_key
            del install_info['plugin_file']
            self.ap.logger.info(f'Transfered file {file_key} to plugin runtime')

        async for ret in self.handler.install_plugin(install_source.value, install_info):
            current_action = ret.get('current_action', None)
            if current_action is not None:
                if task_context is not None:
                    task_context.set_current_action(current_action)

            trace = ret.get('trace', None)
            if trace is not None:
                if task_context is not None:
                    task_context.trace(trace)

    async def upgrade_plugin(
        self, plugin_author: str, plugin_name: str, task_context: taskmgr.TaskContext | None = None
    ) -> dict[str, Any]:
        async for ret in self.handler.upgrade_plugin(plugin_author, plugin_name):
            current_action = ret.get('current_action', None)
            if current_action is not None:
                if task_context is not None:
                    task_context.set_current_action(current_action)

            trace = ret.get('trace', None)
            if trace is not None:
                if task_context is not None:
                    task_context.trace(trace)

    async def delete_plugin(
        self, plugin_author: str, plugin_name: str, task_context: taskmgr.TaskContext | None = None
    ) -> dict[str, Any]:
        async for ret in self.handler.delete_plugin(plugin_author, plugin_name):
            current_action = ret.get('current_action', None)
            if current_action is not None:
                if task_context is not None:
                    task_context.set_current_action(current_action)

            trace = ret.get('trace', None)
            if trace is not None:
                if task_context is not None:
                    task_context.trace(trace)

    async def list_plugins(self) -> list[dict[str, Any]]:
        return await self.handler.list_plugins()

    async def get_plugin_info(self, author: str, plugin_name: str) -> dict[str, Any]:
        return await self.handler.get_plugin_info(author, plugin_name)

    async def set_plugin_config(self, plugin_author: str, plugin_name: str, config: dict[str, Any]) -> dict[str, Any]:
        return await self.handler.set_plugin_config(plugin_author, plugin_name, config)

    @alru_cache(ttl=5 * 60)  # 5 minutes
    async def get_plugin_icon(self, plugin_author: str, plugin_name: str) -> dict[str, Any]:
        return await self.handler.get_plugin_icon(plugin_author, plugin_name)

    async def emit_event(
        self,
        event: events.BaseEventModel,
    ) -> context.EventContext:
        event_ctx = context.EventContext.from_event(event)

        if not self.is_enable_plugin:
            return event_ctx
        event_ctx_result = await self.handler.emit_event(event_ctx.model_dump(serialize_as_any=True))

        event_ctx = context.EventContext.model_validate(event_ctx_result['event_context'])

        return event_ctx

    async def list_tools(self) -> list[ComponentManifest]:
        list_tools_data = await self.handler.list_tools()

        return [ComponentManifest.model_validate(tool) for tool in list_tools_data]

    async def call_tool(self, tool_name: str, parameters: dict[str, Any]) -> dict[str, Any]:
        return await self.handler.call_tool(tool_name, parameters)

    async def list_commands(self) -> list[ComponentManifest]:
        list_commands_data = await self.handler.list_commands()

        return [ComponentManifest.model_validate(command) for command in list_commands_data]

    async def execute_command(
        self, command_ctx: command_context.ExecuteContext
    ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
        gen = self.handler.execute_command(command_ctx.model_dump(serialize_as_any=True))

        async for ret in gen:
            cmd_ret = command_context.CommandReturn.model_validate(ret)

            yield cmd_ret

    def dispose(self):
        if self.is_enable_plugin and isinstance(self.ctrl, stdio_client_controller.StdioClientController):
            self.ap.logger.info('Terminating plugin runtime process...')
            self.ctrl.process.terminate()

        if self.heartbeat_task is not None:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None
