"""Tests for database extensions and configuration."""


class TestBuildDatabaseUrl:
    """Tests for _build_database_url function."""

    def test_defaults_to_sqlite(self, monkeypatch):
        """Should return SQLite URL when no postgres env vars set."""
        monkeypatch.delenv("POSTGRES_HOST", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        from app.extensions import _build_database_url

        url = _build_database_url()
        assert url == "sqlite:////data/corvin.db"

    def test_uses_database_url_env(self, monkeypatch):
        """Should use DATABASE_URL env var for SQLite."""
        monkeypatch.delenv("POSTGRES_HOST", raising=False)
        monkeypatch.setenv("DATABASE_URL", "sqlite:///custom.db")

        from app.extensions import _build_database_url

        url = _build_database_url()
        assert url == "sqlite:///custom.db"

    def test_builds_postgres_url(self, monkeypatch):
        """Should build PostgreSQL URL when POSTGRES_HOST is set."""
        monkeypatch.setenv("POSTGRES_HOST", "localhost")
        monkeypatch.setenv("POSTGRES_USER", "testuser")
        monkeypatch.setenv("POSTGRES_PASSWORD", "testpass")
        monkeypatch.setenv("POSTGRES_DB", "testdb")
        monkeypatch.setenv("POSTGRES_PORT", "5433")

        from app.extensions import _build_database_url

        url = _build_database_url()
        assert url == "postgresql+psycopg2://testuser:testpass@localhost:5433/testdb"

    def test_postgres_defaults(self, monkeypatch):
        """Should use default values for PostgreSQL config."""
        monkeypatch.setenv("POSTGRES_HOST", "db.example.com")
        monkeypatch.delenv("POSTGRES_USER", raising=False)
        monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
        monkeypatch.delenv("POSTGRES_DB", raising=False)
        monkeypatch.delenv("POSTGRES_PORT", raising=False)

        from app.extensions import _build_database_url

        url = _build_database_url()
        assert url == "postgresql+psycopg2://corvin@db.example.com:5432/corvin"

    def test_postgres_url_encodes_special_chars(self, monkeypatch):
        """Should URL-encode special characters in credentials."""
        monkeypatch.setenv("POSTGRES_HOST", "localhost")
        monkeypatch.setenv("POSTGRES_USER", "user@domain")
        monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss:word/123")

        from app.extensions import _build_database_url

        url = _build_database_url()
        assert "user%40domain" in url
        assert "p%40ss%3Aword%2F123" in url


class TestJsonText:
    """Tests for json_text helper function."""

    def test_returns_column_for_sqlite(self, app):
        """Should return column unchanged for SQLite."""
        from unittest.mock import MagicMock, patch

        from app.extensions import json_text

        mock_column = MagicMock()

        with patch("app.extensions.DB_DIALECT", "sqlite"):
            result = json_text(mock_column)

        assert result is mock_column

    def test_casts_column_for_postgres(self, app):
        """Should cast column to String for PostgreSQL."""
        from unittest.mock import MagicMock, patch

        from app.extensions import json_text

        mock_column = MagicMock()

        with patch("app.extensions.DB_DIALECT", "postgresql"):
            result = json_text(mock_column)

        # Result should be a cast expression, not the original column
        assert result is not mock_column


class TestDbDialect:
    """Tests for DB_DIALECT detection."""

    def test_dialect_is_sqlite_for_test_db(self, app):
        """Test database should use SQLite dialect."""
        # The test fixture uses in-memory SQLite
        from app.extensions import DB_DIALECT

        assert DB_DIALECT == "sqlite"


class TestSqlitePragma:
    """Tests for SQLite PRAGMA configuration."""

    def test_network_share_mode_uses_delete_journal(self, monkeypatch):
        """Should use DELETE journal mode when SQLITE_NETWORK_SHARE is set."""
        monkeypatch.setenv("SQLITE_NETWORK_SHARE", "true")

        # Reimport to pick up env var
        import importlib
        from unittest.mock import MagicMock

        import app.extensions

        importlib.reload(app.extensions)

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        app.extensions._set_sqlite_pragma(mock_connection, None)

        # Check that DELETE journal mode was set
        calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert any("DELETE" in str(call) for call in calls)
        assert any("EXCLUSIVE" in str(call) for call in calls)

    def test_default_mode_uses_wal_journal(self, monkeypatch):
        """Should use WAL journal mode by default."""
        monkeypatch.delenv("SQLITE_NETWORK_SHARE", raising=False)

        import importlib
        from unittest.mock import MagicMock

        import app.extensions

        importlib.reload(app.extensions)

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        app.extensions._set_sqlite_pragma(mock_connection, None)

        calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert any("WAL" in str(call) for call in calls)
        assert any("NORMAL" in str(call) for call in calls)


class TestSessionFactories:
    """Tests for session factory configuration."""

    def test_session_local_exists(self, app):
        """SessionLocal should be configured."""
        from app.extensions import SessionLocal

        assert SessionLocal is not None

    def test_read_session_local_exists(self, app):
        """ReadSessionLocal should be configured."""
        from app.extensions import ReadSessionLocal

        assert ReadSessionLocal is not None

    def test_get_db_yields_session(self, app):
        """get_db should yield a database session."""
        from app.extensions import get_db

        gen = get_db()
        session = next(gen)
        assert session is not None

        # Clean up
        try:
            next(gen)
        except StopIteration:
            pass

    def test_get_read_db_yields_session(self, app):
        """get_read_db should yield a database session."""
        from app.extensions import get_read_db

        gen = get_read_db()
        session = next(gen)
        assert session is not None

        # Clean up
        try:
            next(gen)
        except StopIteration:
            pass
