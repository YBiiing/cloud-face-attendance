from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('attendance_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('recognition_tasks.id'), nullable=False, unique=True),
        sa.Column('received_at', DATETIME(fsp=6), nullable=False),
        sa.Column('confirmed_at', DATETIME(fsp=6), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('model_version', sa.String(100), nullable=False),
        sa.UniqueConstraint('session_id', 'user_id', name='uq_attendance_person'),
        sa.ForeignKeyConstraint(['session_id', 'user_id'], ['session_members.session_id', 'session_members.user_id'], name='fk_record_member'),
    )
    op.create_index('ix_attendance_records_session_id', 'attendance_records', ['session_id'])
    op.create_index('ix_attendance_records_user_id', 'attendance_records', ['user_id'])


def downgrade():
    op.drop_table('attendance_records')
