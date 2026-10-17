"""Keep class names unambiguous without merging existing class rosters."""
from alembic import op
import sqlalchemy as sa

revision='0008'
down_revision='0007'
branch_labels=None
depends_on=None


def upgrade():
    duplicate=op.get_bind().execute(sa.text(
        'SELECT 1 FROM classes GROUP BY name HAVING COUNT(*) > 1 LIMIT 1'
    )).first()
    if duplicate:
        raise RuntimeError(
            'Duplicate class names exist. Give each class a distinct name before '
            'retrying migration 0008; preserve class IDs and existing rosters. '
            'No class data has been changed by this migration.'
        )
    op.create_unique_constraint('uq_classes_name','classes',['name'])


def downgrade():
    op.drop_constraint('uq_classes_name','classes',type_='unique')
