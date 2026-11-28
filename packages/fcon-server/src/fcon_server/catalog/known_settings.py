"""The settings an operator owns, per kind, one line each (design decision 5).

Each setting has a value type and the product's default. A value type's parser gives a value's
canonical spelling, the one the store keeps, or says what is expected. The code's values in a
definitions file and an operator's values go through the same `check`. A name the code decides
(`key`, `source`, `write-mode`...) is refused as decided by the code, not by a setting.

Adding a setting is one line in `SETTINGS`; no migration.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from functools import cache
from zoneinfo import available_timezones

NONE = "none"


class Kind(StrEnum):
    """What a catalog entry is: a flow, a dataset or a route."""

    FLOW = "flow"
    DATASET = "dataset"
    ROUTE = "route"


@dataclass(frozen=True, kw_only=True)
class ValueType:
    """A setting's type: what its values look like, and `none` too when `optional`."""

    optional: bool = False

    def canonical(self, text: str) -> str | None:
        """The value's canonical spelling, or None when it is not a value of this type."""
        text = text.strip()
        if self.optional and text == NONE:
            return NONE
        return self._canonical(text)

    @property
    def expected(self) -> str:
        """What a value of this type is, as a phrase: "a length of time, such as 3d or 12h"."""
        return self._expected() + (", or none" if self.optional else "")

    def _canonical(self, text: str) -> str | None:  # pragma: no cover - every type has its own
        """The canonical spelling of a value other than `none`, or None when it is not one."""
        raise NotImplementedError

    def _expected(self) -> str:  # pragma: no cover - every type has its own
        """What a value other than `none` is."""
        raise NotImplementedError


_LENGTH = re.compile(r"(\d{1,9})([smhd])")


@dataclass(frozen=True, kw_only=True)
class Length(ValueType):
    """A length of time in seconds, minutes, hours or days: `90s`, `15m`, `12h`, `3d`."""

    def _canonical(self, text: str) -> str | None:
        """The number without leading zeros, then its unit."""
        found = _LENGTH.fullmatch(text)
        return None if found is None else f"{int(found[1])}{found[2]}"

    def _expected(self) -> str:
        """What a length of time is."""
        return "a length of time, such as 3d or 12h"


@dataclass(frozen=True, kw_only=True)
class Count(ValueType):
    """A whole number from `least` up."""

    least: int

    def _canonical(self, text: str) -> str | None:
        """The number without leading zeros, when it is whole and at least `least`."""
        if not text.isascii() or not text.isdigit() or len(text) > 9 or int(text) < self.least:
            return None
        return str(int(text))

    def _expected(self) -> str:
        """What a count is, with its least value."""
        return f"a whole number from {self.least} up"


@dataclass(frozen=True, kw_only=True)
class Choice(ValueType):
    """One of a fixed set of words."""

    options: tuple[str, ...]

    def _canonical(self, text: str) -> str | None:
        """The word, when it is one of the options."""
        return text if text in self.options else None

    def _expected(self) -> str:
        """The options, the last after "or"."""
        return f"one of {', '.join(self.options[:-1])} or {self.options[-1]}"


@dataclass(frozen=True, kw_only=True)
class Switch(ValueType):
    """`on` or `off`."""

    def _canonical(self, text: str) -> str | None:
        """The word, when it is on or off."""
        return text if text in {"on", "off"} else None

    def _expected(self) -> str:
        """What a switch is."""
        return "on or off"


@cache
def _time_zones() -> frozenset[str]:
    """Every time zone's name, from tzdata on every platform: read once."""
    return frozenset(available_timezones())


@dataclass(frozen=True, kw_only=True)
class TimeZone(ValueType):
    """A time zone's name, as the time zone database spells it: `UTC`, `Europe/Paris`."""

    def _canonical(self, text: str) -> str | None:
        """The name, when the time zone database has it."""
        return text if text in _time_zones() else None

    def _expected(self) -> str:
        """What a time zone is."""
        return "a time zone, such as UTC or Europe/Paris"


_CRON_FIELD = re.compile(r"[0-9*,/-]+")
_CRON_FIELDS = 5


@dataclass(frozen=True, kw_only=True)
class Schedule(ValueType):
    """Five cron fields of digits, `*`, `,`, `-` and `/`; checked for shape, not for ranges."""

    def _canonical(self, text: str) -> str | None:
        """The five fields, one space apart."""
        fields = text.split()
        if len(fields) != _CRON_FIELDS or not all(_CRON_FIELD.fullmatch(field) for field in fields):
            return None
        return " ".join(fields)

    def _expected(self) -> str:
        """What a schedule is."""
        return "five cron fields, such as 0 6 * * *"


@dataclass(frozen=True, kw_only=True)
class Moment(ValueType):
    """A time with its offset, such as a pause's end: `2026-12-01T06:00+00:00`."""

    def _canonical(self, text: str) -> str | None:
        """The time in ISO 8601 to the second, with its offset."""
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            return None
        return None if moment.tzinfo is None else moment.isoformat(timespec="seconds")

    def _expected(self) -> str:
        """What a time with its offset is."""
        return "a time with its offset, such as 2026-12-01T06:00+00:00"


@dataclass(frozen=True)
class Setting:
    """One setting an operator owns: its name, its type and the product's default."""

    name: str
    type: ValueType
    default: str


_SWITCH = Switch()
_LENGTH_OF_TIME = Length()
_RETRIES = Setting("retries", Count(least=0), "3")
_TIME_LIMIT = Setting("time-limit", _LENGTH_OF_TIME, "1h")
_BATCH_SIZE = Setting("batch-size", Count(least=1), "5000")
_PAUSED_UNTIL = Setting("paused-until", Moment(optional=True), NONE)
_ALERT_AFTER_FAILURES = Setting("alert-after-failures", Count(least=1), "1")

SETTINGS: dict[Kind, tuple[Setting, ...]] = {
    Kind.FLOW: (
        Setting("on", _SWITCH, "off"),
        Setting("schedule", Schedule(optional=True), NONE),
        Setting("time-zone", TimeZone(), "UTC"),
        _PAUSED_UNTIL,
        _RETRIES,
        _TIME_LIMIT,
        Setting("parallel-work", Count(least=1), "1"),
        Setting("overlap", Choice(options=("skip", "wait", "allow")), "skip"),
        Setting("catch-up", Choice(options=("latest", "all", "skip")), "latest"),
        _ALERT_AFTER_FAILURES,
    ),
    Kind.DATASET: (
        Setting("look-back", _LENGTH_OF_TIME, "0s"),
        Setting("full-comparison-schedule", Schedule(optional=True), NONE),
        _BATCH_SIZE,
        _RETRIES,
        _TIME_LIMIT,
        Setting("readiness-interval", _LENGTH_OF_TIME, "5m"),
        Setting("late-data", Choice(options=("warn", "accept", "refuse")), "warn"),
        Setting("schema-changes", Choice(options=("ask", "accept", "refuse")), "ask"),
        Setting("alert-when-stale-after", Length(optional=True), NONE),
        Setting("keep-records", _LENGTH_OF_TIME, "14d"),
        Setting("keep-versions", _LENGTH_OF_TIME, "400d"),
        Setting("fetch-batch-size", Count(least=1), "100"),
        Setting("fetch-retries", Count(least=0), "5"),
        Setting("fetch-time-limit", _LENGTH_OF_TIME, "30s"),
    ),
    Kind.ROUTE: (
        Setting("on", _SWITCH, "on"),
        _PAUSED_UNTIL,
        _RETRIES,
        _TIME_LIMIT,
        _BATCH_SIZE,
        Setting("parallel-partitions", Count(least=1), "1"),
        Setting("approval", Choice(options=("never", "always")), "never"),
        Setting("supersede-automatically", _SWITCH, "off"),
        Setting("parent-wait-limit", _LENGTH_OF_TIME, "1d"),
        _ALERT_AFTER_FAILURES,
        Setting("keep-deliveries", _LENGTH_OF_TIME, "180d"),
        Setting("keep-answers", _LENGTH_OF_TIME, "30d"),
    ),
}

# What the code decides, spelled as a setting would be: never a setting.
CODE_DECIDES = frozenset(
    {
        "name",
        "renamed-from",
        "source",
        "key",
        "dataset",
        "write-mode",
        "partitions",
        "partition-scheme",
        "change-detection",
        "shape",
        "event-kind",
        "readiness-set",
        "settings",
    }
)


class SettingRefusedError(Exception):
    """A setting, or a value of one, that cannot be taken."""


class DecidedByCodeError(SettingRefusedError):
    """The name is something the code decides, not a setting."""

    def __init__(self, kind: Kind, setting: str) -> None:
        super().__init__(f"the {setting} of a {kind} is decided by the code")
        self.kind = kind
        self.setting = setting


class UnknownSettingError(SettingRefusedError):
    """The kind has no setting of this name."""

    def __init__(self, kind: Kind, setting: str) -> None:
        super().__init__(f"a {kind} has no setting named {setting}")
        self.kind = kind
        self.setting = setting


class BadValueError(SettingRefusedError):
    """The value is not one of the setting's type; `expected` says, as a sentence, what is."""

    def __init__(self, value: str, setting: str, expected: str) -> None:
        super().__init__(f"{value!r} is not a {setting}")
        self.value = value
        self.setting = setting
        self.expected = expected


type SettingRefusal = DecidedByCodeError | UnknownSettingError | BadValueError
"""Every way `check` refuses a setting or its value."""


def settings_of(kind: Kind) -> tuple[Setting, ...]:
    """The settings of `kind`, in the list's order."""
    return SETTINGS[kind]


def _article(word: str) -> str:
    """The article for `word`: An before a vowel, else A."""
    return "An" if word[0] in "aeiou" else "A"


def check(kind: Kind, setting: str, value: str) -> str:
    """The value's canonical spelling for the setting `setting` of a `kind`.

    Raises `DecidedByCodeError` for a name the code decides, `UnknownSettingError` for a setting
    the kind does not have, and `BadValueError` for a value not of the setting's type.
    """
    if setting.replace("_", "-") in CODE_DECIDES:
        raise DecidedByCodeError(kind, setting)
    known = next((each for each in settings_of(kind) if each.name == setting), None)
    if known is None:
        raise UnknownSettingError(kind, setting)
    canonical = known.type.canonical(value)
    if canonical is None:
        raise BadValueError(value, setting, f"{_article(setting)} {setting} is {known.type.expected}.")
    return canonical
