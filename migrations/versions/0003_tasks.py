from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('recognition_tasks',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('type',sa.String(20),nullable=False),
        sa.Column('status',sa.String(20),nullable=False),
        sa.Column('owner_user_id',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('scope',sa.String(80),nullable=False),
        sa.Column('request_key',sa.String(64),nullable=False),
        sa.Column('request_digest',sa.String(64),nullable=False),
        sa.Column('token_hash',sa.String(64),nullable=False),
        sa.Column('image_path',sa.String(255)),
        sa.Column('payload',sa.JSON(),nullable=False),
        sa.Column('result_code',sa.String(40)),
        sa.Column('created_at',DATETIME(fsp=6),nullable=False),
        sa.Column('received_at',DATETIME(fsp=6),nullable=False),
        sa.Column('expires_at',DATETIME(fsp=6),nullable=False),
        sa.Column('started_at',DATETIME(fsp=6)),
        sa.Column('finished_at',DATETIME(fsp=6)),
        sa.Column('lease_until',DATETIME(fsp=6)),
        sa.Column('attempt_id',sa.String(36)),
        sa.Column('attempts',sa.Integer(),nullable=False),
        sa.UniqueConstraint('scope','request_key',name='uq_task_request'),
        mysql_engine='InnoDB',mysql_charset='utf8mb4')
    for field in ['status','owner_user_id','expires_at']:
        op.create_index('ix_recognition_tasks_'+field,'recognition_tasks',[field])


def downgrade(): op.drop_table('recognition_tasks')
