from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision='0005'
down_revision='0004'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('attendance_sessions',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('title',sa.String(100),nullable=False),
        sa.Column('class_id',sa.Integer(),sa.ForeignKey('classes.id'),nullable=False),
        sa.Column('public_code',sa.String(64),nullable=False),
        sa.Column('starts_at',DATETIME(fsp=6),nullable=False),
        sa.Column('ends_at',DATETIME(fsp=6),nullable=False),
        sa.Column('closed_at',DATETIME(fsp=6)),
        sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_at',DATETIME(fsp=6),nullable=False),
        sa.UniqueConstraint('public_code'),mysql_engine='InnoDB',mysql_charset='utf8mb4')
    op.create_index('ix_attendance_sessions_class_id','attendance_sessions',['class_id'])
    op.create_table('session_members',
        sa.Column('session_id',sa.Integer(),sa.ForeignKey('attendance_sessions.id'),primary_key=True),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),primary_key=True),
        mysql_engine='InnoDB',mysql_charset='utf8mb4')


def downgrade():
    op.drop_table('session_members');op.drop_table('attendance_sessions')
