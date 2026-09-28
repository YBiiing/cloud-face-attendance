"""Initial classes and users."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("classes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("status", sa.Enum("ACTIVE", "DISABLED"), nullable=False),
        sa.Column("created_at", DATETIME(fsp=6), nullable=False),
        mysql_engine="InnoDB", mysql_charset="utf8mb4")
    op.create_table("users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_no", sa.String(32), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id")),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("STUDENT", "ADMIN"), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "ACTIVE", "DISABLED"), nullable=False),
        sa.Column("created_at", DATETIME(fsp=6), nullable=False),
        sa.UniqueConstraint("student_no", name="uq_users_student_no"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4")
    op.create_index("ix_users_class_id", "users", ["class_id"])


def downgrade():
    op.drop_table("users")
    op.drop_table("classes")
