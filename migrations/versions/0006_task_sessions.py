from alembic import op
import sqlalchemy as sa
revision='0006'
down_revision='0005'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('recognition_tasks',sa.Column('session_id',sa.Integer(),nullable=True))
    op.create_foreign_key('fk_task_session','recognition_tasks','attendance_sessions',['session_id'],['id'])
    op.create_index('ix_recognition_tasks_session_id','recognition_tasks',['session_id'])


def downgrade():
    op.drop_constraint('fk_task_session','recognition_tasks',type_='foreignkey')
    op.drop_index('ix_recognition_tasks_session_id',table_name='recognition_tasks')
    op.drop_column('recognition_tasks','session_id')
