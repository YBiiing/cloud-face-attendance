from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('login_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('expires_at', DATETIME(fsp=6), nullable=False),
        sa.UniqueConstraint('token_hash'), mysql_engine='InnoDB', mysql_charset='utf8mb4')
    op.create_index('ix_login_sessions_user_id', 'login_sessions', ['user_id'])
    op.create_index('ix_login_sessions_expires_at', 'login_sessions', ['expires_at'])


def downgrade():
    op.drop_table('login_sessions')
