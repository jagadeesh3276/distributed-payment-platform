
revision = "31b586209364"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    # Compatibility bridge for the existing database revision.
    # Intentionally makes no database changes.
    pass


def downgrade():
    # Intentionally makes no database changes.
    pass
