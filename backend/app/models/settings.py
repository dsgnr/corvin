"""Settings model"""

from sqlalchemy import Column, String, Text

from app.models import Base


class Settings(Base):
    """
    Key-value settings store.

    Used for persisting configuration that needs to survive restarts,
    such as worker pause states.
    """

    __tablename__ = "settings"

    key = Column(String(50), primary_key=True)
    value = Column(Text, nullable=False, default="")

    @classmethod
    def get(cls, db, key: str, default: str = "") -> str:
        """
        Get a setting value.

        Args:
            db: Database session.
            key: The setting key.
            default: Default value if not found.

        Returns:
            The setting value or default.
        """
        setting = db.query(cls).get(key)
        return setting.value if setting else default

    @classmethod
    def get_bool(cls, db, key: str, default: bool = False) -> bool:
        """
        Get a boolean setting value.

        Args:
            db: Database session.
            key: The setting key.
            default: Default value if not found.

        Returns:
            The boolean value.
        """
        value = cls.get(db, key, str(default).lower())
        return value.lower() in ("true", "1", "yes")

    @classmethod
    def set(cls, db, key: str, value: str, commit: bool = True) -> None:
        """
        Set a setting value.

        Args:
            db: Database session.
            key: The setting key.
            value: The value to store.
            commit: Whether to commit the transaction.
        """
        setting = db.query(cls).get(key)
        if setting:
            setting.value = value
        else:
            setting = cls(key=key, value=value)
            db.add(setting)
        if commit:
            db.commit()

    @classmethod
    def set_bool(cls, db, key: str, value: bool, commit: bool = True) -> None:
        """
        Set a boolean setting value.

        Args:
            db: Database session.
            key: The setting key.
            value: The boolean value to store.
            commit: Whether to commit the transaction.
        """
        cls.set(db, key, "true" if value else "false", commit=commit)
