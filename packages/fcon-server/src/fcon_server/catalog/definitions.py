"""Reading one package version's definitions (design § How it is built, A definitions file).

A definitions file is JSON: `package`, `version`, and the lists `flows`, `datasets` and `routes`,
each item an object with a `name`, optionally `renamed_from` and `settings` (the code's values
of operator settings). Everything else in an item is what the code decides; it is kept whole,
never read. Names, the version and every code value are checked here, at the edge; the code's
values are kept in their canonical spelling. The checksum is the SHA-256 of one canonical JSON
spelling, so the same definitions always have the same one.

What needs the catalog (a kind that changes, a rename across kinds) is checked by `recording`.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import cast

from fcon_server.catalog.known_settings import Kind, SettingRefusedError, check

LARGEST = 1_000_000  # bytes in a definitions file
GROUPS = {"flows": Kind.FLOW, "datasets": Kind.DATASET, "routes": Kind.ROUTE}
_KEYS = {"package", "version", *GROUPS}
_PACKAGE = re.compile(r"[a-z][a-z0-9-]{0,63}")
_LOCAL_NAME = re.compile(r"[a-z][a-z0-9_-]{0,63}")
_LONGEST_VERSION = 64
_THE_SHAPE = "Give one JSON object: package, version, and lists of flows, datasets and routes."

type JsonObject = dict[str, object]


class NotDefinitionsError(Exception):
    """The file or data is not a package version's definitions: `what` is wrong, `expected` says what is wanted."""

    def __init__(self, what: str, expected: str) -> None:
        super().__init__(what)
        self.what = what
        self.expected = expected


class CodeValueError(Exception):
    """The code gives the entry `name` a setting it cannot have, or a value of the wrong type."""

    def __init__(self, name: str, refused: SettingRefusedError) -> None:
        super().__init__(f"{name}: {refused}")
        self.name = name
        self.refused = refused


@dataclass(frozen=True)
class Definition:
    """One flow, dataset or route as a package version declares it.

    `settings` are the code's values, canonically spelled; `body` is the whole item, with them.
    """

    kind: Kind
    name: str
    renamed_from: str | None
    settings: dict[str, str]
    body: JsonObject


@dataclass(frozen=True)
class PackageDefinitions:
    """Everything one package version declares, in the file's order, with its checksum."""

    package: str
    version: str
    definitions: tuple[Definition, ...]
    checksum: str


def _shown(value: object) -> str:
    """A value as JSON spells it, for a message."""
    return json.dumps(value, ensure_ascii=False)


def _as_object(value: object) -> JsonObject | None:
    """The value as a JSON object, or None when it is not one; JSON's keys are always text."""
    return cast(JsonObject, value) if isinstance(value, dict) else None


def parse_definitions(raw: bytes) -> PackageDefinitions:
    """Reads a definitions file's bytes: at most `LARGEST`, UTF-8 JSON, then `read_definitions`.

    Raises `NotDefinitionsError` or `CodeValueError`.
    """
    if len(raw) > LARGEST:
        raise NotDefinitionsError("it is larger than 1 MB", "A definitions file is at most 1 MB.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise NotDefinitionsError("it is not UTF-8", "Save it as UTF-8 JSON.") from None
    try:
        data: object = json.loads(text)
    except json.JSONDecodeError as err:
        what = f"it is not JSON ({err.msg} at line {err.lineno}, column {err.colno})"
        raise NotDefinitionsError(what, _THE_SHAPE) from None
    return read_definitions(data)


def _package(top: JsonObject) -> str:
    """The package's name, checked against its rule."""
    package = top.get("package")
    if not isinstance(package, str) or not _PACKAGE.fullmatch(package):
        raise NotDefinitionsError(
            f"the package {_shown(package)} is not a package name",
            "A package name is 1 to 64 of a-z, 0-9 and -, starting with a letter.",
        )
    return package


def _version(top: JsonObject) -> str:
    """The version, checked: 1 to 64 printable characters, no spaces."""
    version = top.get("version")
    if (
        not isinstance(version, str)
        or not 1 <= len(version) <= _LONGEST_VERSION
        or not version.isprintable()
        or any(character.isspace() for character in version)
    ):
        raise NotDefinitionsError(
            f"the version {_shown(version)} is not a version", "A version is 1 to 64 printable characters, no spaces."
        )
    return version


def _is_name_of(package: str, name: object) -> bool:
    """Whether `name` is a full name of `package`: the package's name, a dot, a local name."""
    if not isinstance(name, str):
        return False
    prefix, dot, local = name.partition(".")
    return prefix == package and dot == "." and _LOCAL_NAME.fullmatch(local) is not None


def _settings(kind: Kind, name: str, item: JsonObject) -> dict[str, str]:
    """The code's values in the item, each checked and canonically spelled."""
    given = item.get("settings", {})
    settings = _as_object(given)
    if settings is None:
        raise NotDefinitionsError(
            f"the settings of {name} are not an object",
            "Give settings as an object of setting names and values, each a text or a whole number.",
        )
    canonical: dict[str, str] = {}
    for setting, value in settings.items():
        if isinstance(value, bool) or not isinstance(value, str | int):
            raise NotDefinitionsError(
                f"the {setting} of {name} is not a text or a whole number",
                "Give each setting's value as a text or a whole number.",
            )
        try:
            canonical[setting] = check(kind, setting, str(value))
        except SettingRefusedError as err:
            raise CodeValueError(name, err) from None
    return canonical


def _definition(package: str, kind: Kind, item: JsonObject) -> Definition:
    """One item read: its name and rename checked, its code values canonical."""
    name = item.get("name")
    if not _is_name_of(package, name):
        raise NotDefinitionsError(
            f"the name {_shown(name)} is not a name of {package}",
            f"A name is {package}. then 1 to 64 of a-z, 0-9, - and _, starting with a letter.",
        )
    name = cast(str, name)
    renamed_from = item.get("renamed_from")
    if renamed_from is not None and not _is_name_of(package, renamed_from):
        raise NotDefinitionsError(
            f"{name} is renamed from {renamed_from}, which is not a name of {package}",
            "A rename names a flow, dataset or route of the same package.",
        )
    settings = _settings(kind, name, item)
    body = {**item, "settings": settings} if "settings" in item else dict(item)
    return Definition(kind, name, cast(str | None, renamed_from), settings, body)


def _items(top: JsonObject, group: str) -> list[JsonObject]:
    """The objects of one list, `flows`, `datasets` or `routes`; none when it is left out."""
    given = top.get(group, [])
    if not isinstance(given, list):
        raise NotDefinitionsError(f"{group} is not a list", f"Give {group} as a list of objects, each with a name.")
    items: list[JsonObject] = []
    for each in cast(list[object], given):
        item = _as_object(each)
        if item is None:
            raise NotDefinitionsError(
                f"an item of {group} is not an object", f"Give {group} as a list of objects, each with a name."
            )
        items.append(item)
    return items


def _check_names(definitions: list[Definition]) -> None:
    """Refuses a name declared twice, and a rename whose old name this version still declares."""
    declared: set[str] = set()
    for each in definitions:
        if each.name in declared:
            raise NotDefinitionsError(
                f"{each.name} is declared twice", "Give each flow, dataset and route its own name."
            )
        declared.add(each.name)
    for each in definitions:
        if each.renamed_from in declared:
            raise NotDefinitionsError(
                f"{each.name} is renamed from {each.renamed_from}, which this version still declares",
                "Declare the old name no more, or leave out renamed_from.",
            )


def _checksum(package: str, version: str, definitions: list[Definition]) -> str:
    """The SHA-256 of the definitions in one canonical JSON spelling: keys sorted, no spaces."""
    canonical: JsonObject = {"package": package, "version": version}
    for group, kind in GROUPS.items():
        canonical[group] = [each.body for each in definitions if each.kind is kind]
    spelled = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(spelled.encode()).hexdigest()


def read_definitions(data: object) -> PackageDefinitions:
    """Reads one package version's definitions from parsed JSON.

    Raises `NotDefinitionsError` for data that breaks a rule of the file, and `CodeValueError` for
    a code value that is wrong, unknown, or decided by the code.
    """
    top = _as_object(data)
    if top is None:
        raise NotDefinitionsError("it is not a JSON object", _THE_SHAPE)
    if unknown := sorted(set(top) - _KEYS):
        raise NotDefinitionsError(
            f"it has an unknown key {_shown(unknown[0])}",
            "A definitions file has package, version, flows, datasets and routes, nothing else.",
        )
    package, version = _package(top), _version(top)
    definitions = [_definition(package, kind, item) for group, kind in GROUPS.items() for item in _items(top, group)]
    _check_names(definitions)
    return PackageDefinitions(package, version, tuple(definitions), _checksum(package, version, definitions))
