"""Application settings stored in database."""

from app.extensions import db


class Settings(db.Model):
    """Key-value settings store."""

    __tablename__ = "settings"

    key: str = db.Column(db.String(50), primary_key=True)
    value: str = db.Column(db.Text, nullable=False, default="")

    @classmethod
    def get(cls, key: str, default: str = "") -> str:
        """Get a setting value."""
        setting = cls.query.get(key)
        return setting.value if setting else default

    @classmethod
    def get_bool(cls, key: str, default: bool = False) -> bool:
        """Get a boolean setting value."""
        value = cls.get(key, str(default).lower())
        return value.lower() in ("true", "1", "yes")

    @classmethod
    def set(cls, key: str, value: str, commit: bool = True) -> None:
        """Set a setting value."""
        setting = cls.query.get(key)
        if setting:
            setting.value = value
        else:
            setting = cls(key=key, value=value)
            db.session.add(setting)
        if commit:
            db.session.commit()

    @classmethod
    def set_bool(cls, key: str, value: bool, commit: bool = True) -> None:
        """Set a boolean setting value."""
        cls.set(key, "true" if value else "false", commit=commit)
