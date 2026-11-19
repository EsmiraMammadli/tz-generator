import pytest

from app import db


@pytest.mark.parametrize("raw,expected", [
    ("postgres://u:p@host:5432/d?sslmode=require", "postgresql+psycopg://u:p@host:5432/d?sslmode=require"),
    ("postgresql://u:p@host/d", "postgresql+psycopg://u:p@host/d"),
    ("postgresql+psycopg://u:p@host/d", "postgresql+psycopg://u:p@host/d"),  # artıq düzgündür
    ("sqlite:///./x.db", "sqlite:///./x.db"),
])
def test_normalize_url(raw, expected):
    assert db.normalize_url(raw) == expected


def test_engine_kwargs_per_backend():
    assert db._engine_kwargs("sqlite:///x")["connect_args"] == {"check_same_thread": False}
    pg = db._engine_kwargs("postgresql+psycopg://u:p@h/d")
    assert pg["pool_pre_ping"] and pg["connect_args"] == {"prepare_threshold": None} and pg["pool_size"] <= 5
