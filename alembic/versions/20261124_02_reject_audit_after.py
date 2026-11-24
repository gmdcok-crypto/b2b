"""변경 이력(audit_logs)의 단가 반려 행 이후 값을 이전 값과 같게 맞춘다.

Revision ID: 20261124_02
Revises: 20261124_01
Create Date: 2026-11-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261124_02"
down_revision: str | None = "20261124_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE audit_logs SET after_text = before_text "
        "WHERE action = '반려' AND before_text IS NOT NULL AND before_text != ''"
    )


def downgrade() -> None:
    pass
