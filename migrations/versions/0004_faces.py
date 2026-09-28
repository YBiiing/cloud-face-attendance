from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision='0004'
down_revision='0003'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('face_samples',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('image_path',sa.String(255),nullable=False),
        sa.Column('embedding',sa.LargeBinary(),nullable=False),
        sa.Column('dimension',sa.Integer(),nullable=False),
        sa.Column('dtype',sa.String(20),nullable=False),
        sa.Column('model_version',sa.String(100),nullable=False),
        sa.Column('status',sa.String(20),nullable=False),
        sa.Column('created_at',DATETIME(fsp=6),nullable=False),
        mysql_engine='InnoDB',mysql_charset='utf8mb4')
    op.create_index('ix_face_samples_user_id','face_samples',['user_id'])
    op.create_index('ix_face_samples_status','face_samples',['status'])
    op.create_table('face_library_state',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('version',sa.Integer(),nullable=False),sa.Column('updated_at',DATETIME(fsp=6),nullable=False),
        mysql_engine='InnoDB',mysql_charset='utf8mb4')
    op.execute("INSERT INTO face_library_state (id, version, updated_at) VALUES (1, 0, UTC_TIMESTAMP(6))")


def downgrade():
    op.drop_table('face_samples');op.drop_table('face_library_state')
