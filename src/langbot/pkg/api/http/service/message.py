from __future__ import annotations

import typing
import datetime

import sqlalchemy

from ....entity.persistence import message as persistence_message
from ....core import app


class MessageHistoryService:
    """Message history service"""

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def save_message(
        self,
        bot_uuid: str,
        pipeline_uuid: str,
        launcher_type: str,
        launcher_id: typing.Union[int, str],
        sender_id: typing.Union[int, str],
        message_role: str,
        message_content: str,
        message_chain: list[dict],
        query_id: typing.Optional[int] = None,
    ) -> int:
        """Save a message to the database

        Args:
            bot_uuid: Bot UUID
            pipeline_uuid: Pipeline UUID
            launcher_type: Launcher type (e.g., 'person', 'group')
            launcher_id: Launcher ID (e.g., user ID, group ID)
            sender_id: Sender ID
            message_role: Message role ('user' or 'assistant')
            message_content: String representation of the message
            message_chain: Full message chain as list of dicts
            query_id: Optional query ID from pipeline processing

        Returns:
            The ID of the saved message
        """
        stmt = sqlalchemy.insert(persistence_message.MessageHistory).values(
            bot_uuid=bot_uuid,
            pipeline_uuid=pipeline_uuid,
            launcher_type=str(launcher_type),
            launcher_id=str(launcher_id),
            sender_id=str(sender_id),
            message_role=message_role,
            message_content=message_content,
            message_chain=message_chain,
            query_id=query_id,
        )

        result = await self.ap.persistence_mgr.execute_async(stmt)
        return result.lastrowid

    async def get_conversation_history(
        self,
        bot_uuid: typing.Optional[str] = None,
        launcher_type: typing.Optional[str] = None,
        launcher_id: typing.Optional[typing.Union[int, str]] = None,
        sender_id: typing.Optional[typing.Union[int, str]] = None,
        pipeline_uuid: typing.Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        since: typing.Optional[datetime.datetime] = None,
    ) -> list[dict]:
        """Get conversation history with filters

        Args:
            bot_uuid: Optional bot UUID filter
            launcher_type: Optional launcher type filter
            launcher_id: Optional launcher ID filter
            sender_id: Optional sender ID filter
            pipeline_uuid: Optional pipeline UUID filter
            limit: Maximum number of messages to return
            offset: Offset for pagination
            since: Optional datetime to filter messages after

        Returns:
            List of message dictionaries
        """
        stmt = sqlalchemy.select(persistence_message.MessageHistory)

        if bot_uuid:
            stmt = stmt.where(persistence_message.MessageHistory.bot_uuid == bot_uuid)
        if launcher_type:
            stmt = stmt.where(persistence_message.MessageHistory.launcher_type == launcher_type)
        if launcher_id:
            stmt = stmt.where(persistence_message.MessageHistory.launcher_id == str(launcher_id))
        if sender_id:
            stmt = stmt.where(persistence_message.MessageHistory.sender_id == str(sender_id))
        if pipeline_uuid:
            stmt = stmt.where(persistence_message.MessageHistory.pipeline_uuid == pipeline_uuid)
        if since:
            stmt = stmt.where(persistence_message.MessageHistory.created_at >= since)

        stmt = stmt.order_by(persistence_message.MessageHistory.created_at.desc()).limit(limit).offset(offset)

        result = await self.ap.persistence_mgr.execute_async(stmt)
        rows = result.fetchall()

        return [self.ap.persistence_mgr.serialize_model(persistence_message.MessageHistory, row) for row in rows]

    async def get_inactive_conversations(
        self,
        bot_uuid: typing.Optional[str] = None,
        inactive_hours: int = 24,
        limit: int = 50,
    ) -> list[dict]:
        """Get conversations that have been inactive for a specified time

        Args:
            bot_uuid: Optional bot UUID filter
            inactive_hours: Number of hours of inactivity to consider
            limit: Maximum number of conversations to return

        Returns:
            List of conversation info with latest message time
        """
        # Calculate the cutoff time
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=inactive_hours)

        # Build subquery to get latest message time for each conversation
        subquery = (
            sqlalchemy.select(
                persistence_message.MessageHistory.bot_uuid,
                persistence_message.MessageHistory.launcher_type,
                persistence_message.MessageHistory.launcher_id,
                sqlalchemy.func.max(persistence_message.MessageHistory.created_at).label('last_message_time'),
            )
            .group_by(
                persistence_message.MessageHistory.bot_uuid,
                persistence_message.MessageHistory.launcher_type,
                persistence_message.MessageHistory.launcher_id,
            )
            .subquery()
        )

        # Query for conversations with last message before cutoff time
        stmt = sqlalchemy.select(subquery).where(subquery.c.last_message_time < cutoff_time)

        if bot_uuid:
            stmt = stmt.where(subquery.c.bot_uuid == bot_uuid)

        stmt = stmt.order_by(subquery.c.last_message_time.desc()).limit(limit)

        result = await self.ap.persistence_mgr.execute_async(stmt)
        rows = result.fetchall()

        return [
            {
                'bot_uuid': row.bot_uuid,
                'launcher_type': row.launcher_type,
                'launcher_id': row.launcher_id,
                'last_message_time': row.last_message_time.isoformat() if row.last_message_time else None,
            }
            for row in rows
        ]

    async def delete_conversation_history(
        self,
        bot_uuid: str,
        launcher_type: str,
        launcher_id: typing.Union[int, str],
    ) -> int:
        """Delete conversation history for a specific conversation

        Args:
            bot_uuid: Bot UUID
            launcher_type: Launcher type
            launcher_id: Launcher ID

        Returns:
            Number of messages deleted
        """
        stmt = (
            sqlalchemy.delete(persistence_message.MessageHistory)
            .where(persistence_message.MessageHistory.bot_uuid == bot_uuid)
            .where(persistence_message.MessageHistory.launcher_type == launcher_type)
            .where(persistence_message.MessageHistory.launcher_id == str(launcher_id))
        )

        result = await self.ap.persistence_mgr.execute_async(stmt)
        return result.rowcount
