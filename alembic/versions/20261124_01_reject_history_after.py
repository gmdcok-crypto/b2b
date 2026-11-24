"""단가 반려 이력의 이후 단가를 이전 단가와 같게 맞춘다.

반려는 단가를 바꾸지 않으므로 이전 시스템에서 요청 단가로 남아 있던
반려 이력의 after_amount 를 before_amount(당시 적용 단가)로 정정한다.

Revision ID: 20261124_01
Revises: 20261123_01
Create Date: 2026-11-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261124_01"
down_revision: str | None = "20261123_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE price_histories SET after_amount = before_amount "
        "WHERE entry_type = '반려' AND before_amount IS NOT NULL"
    )


def downgrade() -> None:
    # 정정 전 요청 단가는 복원할 수 없으므로 되돌리지 않는다.
    pass
