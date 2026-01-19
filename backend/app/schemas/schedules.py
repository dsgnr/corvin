"""Download schedule schemas."""

from pydantic import BaseModel, field_validator


class ScheduleCreate(BaseModel):
    """Schema for creating a download schedule."""

    name: str
    enabled: bool = True
    days_of_week: list[str]
    start_time: str  # HH:MM format
    end_time: str  # HH:MM format

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, v: list[str]) -> list[str]:
        valid_days = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        for day in v:
            if day.lower() not in valid_days:
                raise ValueError(f"Invalid day: {day}")
        return [d.lower() for d in v]

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time(cls, v: str) -> str:
        try:
            parts = v.split(":")
            if len(parts) != 2:
                raise ValueError()
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError()
        except (ValueError, IndexError) as ex:
            raise ValueError("Time must be in HH:MM format (00:00 - 23:59)") from ex
        return v


class ScheduleUpdate(BaseModel):
    """Schema for updating a download schedule."""

    name: str | None = None
    enabled: bool | None = None
    days_of_week: list[str] | None = None
    start_time: str | None = None
    end_time: str | None = None

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        valid_days = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        for day in v:
            if day.lower() not in valid_days:
                raise ValueError(f"Invalid day: {day}")
        return [d.lower() for d in v]

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            parts = v.split(":")
            if len(parts) != 2:
                raise ValueError()
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError()
        except (ValueError, IndexError):
            raise ValueError("Time must be in HH:MM format (00:00 - 23:59)") from None
        return v


class ScheduleResponse(BaseModel):
    """Schema for schedule response."""

    id: int
    name: str
    enabled: bool
    days_of_week: list[str]
    start_time: str
    end_time: str
    created_at: str
    updated_at: str


class ScheduleStatusResponse(BaseModel):
    """Schema for schedule status check."""

    downloads_allowed: bool
    active_schedules: int
