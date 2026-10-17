from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from fastapi import Request
from sqlalchemy.orm import Session

from gestao_recebiveis.auth import current_user
from gestao_recebiveis.config import get_settings
from gestao_recebiveis.errors import DomainError
from gestao_recebiveis.models import LoginSession, User


@pytest.fixture(autouse=True)
def bootstrap() -> None:
    """Header validation supplies the session reads without a PostgreSQL fixture."""


@pytest.mark.parametrize(
    "token,accepted",
    [(b"\xff", False), (b"incorrect", False), (b"", False), (b"expected-token", True)],
)
def test_csrf_header_validation(token: bytes, accepted: bool) -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "headers": [
                (b"origin", get_settings().frontend_origin.encode()),
                (b"cookie", b"cf_session=synthetic-session"),
                (b"x-csrf-token", token),
            ],
        }
    )
    db = Mock(spec=Session)
    db.get.side_effect = [
        LoginSession(
            token_hash="synthetic-digest",
            user_id=1,
            csrf_token="expected-token",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
        User(id=1, email="user@example.com", name="User", role="operator", is_demo=False),
    ]

    if accepted:
        assert current_user(request, db).id == 1
    else:
        with pytest.raises(DomainError) as failure:
            current_user(request, db)
        assert failure.value.status == 403
        assert failure.value.code == "csrf"
