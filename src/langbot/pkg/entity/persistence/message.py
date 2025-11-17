import sqlalchemy

from .base import Base


class MessageHistory(Base):
    """Message History"""

    __tablename__ = 'message_history'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    bot_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    pipeline_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    launcher_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, index=True)
    launcher_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    sender_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    message_role = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)
    """Role of the message sender: 'user' or 'assistant'"""
    message_content = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    """String representation of the message content"""
    message_chain = sqlalchemy.Column(sqlalchemy.JSON, nullable=False)
    """Full message chain in JSON format"""
    query_id = sqlalchemy.Column(sqlalchemy.Integer, nullable=True)
    """Query ID from the pipeline processing"""
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now(), index=True)
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )
