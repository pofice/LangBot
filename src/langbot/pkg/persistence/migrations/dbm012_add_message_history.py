from .. import migration


@migration.migration_class(12)
class DBMigrateAddMessageHistory(migration.DBMigration):
    """Add message_history table for storing conversation messages"""

    async def upgrade(self):
        """Upgrade"""
        # The table will be automatically created by the Base.metadata.create_all()
        # in the persistence manager initialization, so we don't need to do anything here
        pass

    async def downgrade(self):
        """Downgrade"""
        # We don't support downgrade for this migration
        pass
