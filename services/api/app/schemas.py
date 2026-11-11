from datetime import date
import re
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


OrgRole = Literal["administrator", "member"]
ProjectRole = Literal["project_manager", "planner", "site_engineer", "supervisor", "quantity_surveyor", "executive", "subcontractor", "guest"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def valid_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Use a valid IANA timezone, such as Pacific/Port_Moresby")
    return value


class OrganizationIn(StrictModel):
    name: str = Field(min_length=2, max_length=160)
    timezone: str = "Pacific/Port_Moresby"
    _tz = field_validator("timezone")(valid_timezone)


class ProjectIn(OrganizationIn):
    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    start_date: date
    discipline: str = Field(min_length=2, max_length=60)


class ProjectPatch(StrictModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    archived: bool | None = None

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Provide at least one non-null change")
        return self


class InvitationIn(StrictModel):
    email: str = Field(max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    role: OrgRole = "member"

    @field_validator("email")
    @classmethod
    def lower(cls, value):
        return value.lower()


class MemberPatch(StrictModel):
    role: OrgRole
    active: bool


class ProjectMemberIn(StrictModel):
    user_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    role: ProjectRole
    active: bool = True


class CalendarIn(StrictModel):
    name: str = Field(min_length=2, max_length=160)
    timezone: str = "Pacific/Port_Moresby"
    nominal_minutes_per_day: int = Field(default=480, ge=1, le=1440, strict=True)
    # ISO weekdays 1=Monday, 7=Sunday. Overnight shifts split across days.
    week: dict[str, list[list[str]]]
    exceptions: dict[str, list[list[str]]] = Field(default_factory=dict)
    _tz = field_validator("timezone")(valid_timezone)

    @model_validator(mode="after")
    def valid_intervals(self):
        if set(self.week) != set("1234567"):
            raise ValueError("Week must contain all ISO weekdays 1–7")
        if not any(self.week.values()):
            raise ValueError("Calendar must contain working time")
        if len(self.exceptions) > 3660:
            raise ValueError("Too many calendar exceptions")
        for key in self.exceptions:
            if date.fromisoformat(key).isoformat() != key:
                raise ValueError("Exception keys must be ISO dates")
        for intervals in [*self.week.values(), *self.exceptions.values()]:
            last = -1
            for interval in intervals:
                if len(interval) != 2:
                    raise ValueError("Each shift needs start and finish")
                values = []
                for time in interval:
                    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d|24:00", time):
                        raise ValueError("Shift times use HH:MM; 24:00 is a finish boundary")
                    h, m = map(int, time.split(":"))
                    values.append(60*h + m)
                a, b = values
                if a >= b or a < last:
                    raise ValueError("Shifts must be ordered, nonoverlapping and have positive duration")
                last = b
        return self

