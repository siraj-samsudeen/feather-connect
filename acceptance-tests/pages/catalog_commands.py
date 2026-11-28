"""The developer's and the operator's terminal for the catalog and its
settings: `fcon catalog record <file>` and `fcon catalog list`, `fcon settings
show|set|clear|list`, and what they printed. The commands, their flags, the
definitions files, the output's shape and the texts the steps rely on live
here; the steps only ask questions.

A package version's definitions reach the product as a definitions file (JSON),
the one `fcon catalog record` reads: this page object writes one per version,
built from what the scenario's words say the code declares, into a folder of
the scenario's own. Every scenario reuses the package "shop-flows", so each
runs on a database of its own, upgraded with `fcon db upgrade` the first time
it records (World.own_database). "A protected environment" is FCON_PROTECTED=on
on every command of the scenario.
"""

import json
import re
import shutil
import tempfile
from pathlib import Path

from pages.database_commands import Result
from support import stack

CATALOG = "catalog"
RECORD = "record"
SETTINGS = "settings"
LIST = "list"
SHOW = "show"
SET = "set"
CLEAR = "clear"
REASON_FLAG = "--reason"
DATABASE_SETTING = "FCON_DATABASE_URL"
PROTECTED_SETTING = "FCON_PROTECTED"
PROTECTED_ON = "on"
REFUSED_EXIT = 2

# The setting a scenario's words name, as the commands name it.
SETTING_NAMES = {"look-back": "look-back", "batch size": "batch-size", "retries": "retries", "key": "key"}
# Who a scenario says set a value, as the SET BY column says it.
SET_BY = {"the operator": "operator", "the code": "code", "the product's default": "default"}
OPERATOR = "operator"
# What a dataset's settings line must name at least (the settings list of the design).
DATASET_SETTINGS_NAMED = ("look-back", "batch-size", "retries")

# `fcon catalog list` and `fcon settings show|list`: headings, then one line per
# row, the columns apart by two spaces or more.
COLUMNS = re.compile(r"\s{2,}")
CATALOG_HEADINGS = ("NAME", "KIND", "PACKAGE VERSION")
SHOW_HEADINGS = ("SETTING", "VALUE", "SET BY")
LIST_HEADINGS = ("NAME", "SETTING", "VALUE", "NOTE")
NO_LONGER_IN_THE_CODE = "no longer in the code"

ALREADY_RECORDED_OTHERWISE = "error: %s is recorded already, with other definitions."
NEVER_CHANGES = "  A recorded version never changes: give the changed code a new version."
ALREADY_RECORDED = "%s is recorded already."
NO_LONGER_HAS = "warning: the operator's %s of %s is for a name the code no longer has."
CLEAR_IT = "  Clear it with: fcon settings clear %s %s"
DECIDED_BY_CODE = "error: the %s of %s is decided by the code, not by a setting."
DATASET_SETTINGS = "  A dataset's settings: "
NOT_A_LOOK_BACK = 'error: "%s" is not a look-back.'
LOOK_BACK_IS = "  A look-back is a length of time, such as 3d or 12h."
NEEDS_A_REASON = "%s was not changed: a protected environment needs a reason for every change."
SAY_WHY = "  Say why with --reason."

# The package every scenario declares, and what its version 1.0 holds.
FLOW = "daily"
DATASET = "orders"
ROUTE = "orders-to-crm"
SOURCE = "shop-api.orders"
KEY = ["order_id"]
OTHER_KEY = ["order_number"]  # a dataset "declared differently"
WRITE_MODE = "upsert"


def _setting_value(text):
    """A scenario's "5000" is the code's integer; "1d" stays text."""
    return int(text) if text.isdigit() else text


def split_version(package_version):
    """"shop-flows 1.0" -> ("shop-flows", "1.0")."""
    package, version = package_version.split(" ")
    return package, version


class CatalogCommands:
    def __init__(self, world):
        self.world = world
        self.protected = False
        self.result = None
        self.record_result = None  # the latest `fcon catalog record`
        self.results = []  # every command of the scenario, in order
        self.recorded_version = None  # "shop-flows 1.0": the latest version recorded
        self.last_set = None  # (name, setting, value) of the latest `fcon settings set`
        self.files = {}  # "shop-flows 1.0" -> the first definitions file recorded for it
        self._folder = None

    # -- the scenario's environment ----------------------------------------

    def use_protected_environment(self):
        self.protected = True
        self.world.screen.note("%s=%s: a protected environment" % (PROTECTED_SETTING, PROTECTED_ON))

    def _settings(self):
        if self.world.scenario_database is None:
            self.world.own_database(upgraded=True)
        settings = {DATABASE_SETTING: self.world.scenario_database}
        if self.protected:
            settings[PROTECTED_SETTING] = PROTECTED_ON
        return settings

    def _run(self, arguments):
        process = stack.start_fcon(arguments, self._settings())
        code, out, err, timed_out = stack.finish_fcon(process)
        result = Result(" ".join(arguments), code, out, err, timed_out)
        self.world.screen.command("fcon " + result.command, out + err, code)
        self.results.append(result)
        self.result = result
        return result

    def close(self):
        if self._folder is not None:
            shutil.rmtree(self._folder, ignore_errors=True)

    # -- definitions files -------------------------------------------------

    def definitions(self, package_version, dataset_settings=None, dataset=DATASET, renamed_from=None,
                    differently=False, with_dataset=True):  # fmt: skip
        """What a package version declares: the flow, the dataset (its local
        name, settings, the name it replaces, and another key when declared
        differently) and its route; with with_dataset False, the flow alone."""
        package, version = split_version(package_version)
        full = lambda local: "%s.%s" % (package, local)  # noqa: E731 - a name inside the package
        declared = {
            "package": package,
            "version": version,
            "flows": [{"name": full(FLOW)}],
            "datasets": [],
            "routes": [],
        }
        if with_dataset:
            item = {"name": full(dataset), "source": SOURCE, "key": OTHER_KEY if differently else KEY}
            if renamed_from is not None:
                item["renamed_from"] = renamed_from
            if dataset_settings:
                item["settings"] = {SETTING_NAMES[k]: _setting_value(v) for k, v in dataset_settings.items()}
            declared["datasets"].append(item)
            declared["routes"].append({"name": full(ROUTE), "dataset": full(dataset), "write_mode": WRITE_MODE})
        return declared

    def _write(self, declared):
        if self._folder is None:
            self._folder = Path(tempfile.mkdtemp(prefix="fcon-definitions-"))
        path = self._folder / ("%s-%s-%d.json" % (declared["package"], declared["version"], len(self.results)))
        path.write_text(json.dumps(declared, indent=2), encoding="utf-8")
        return path

    # -- the commands ------------------------------------------------------

    def record(self, declared):
        """`fcon catalog record <file>`, the file holding `declared`."""
        path = self._write(declared)
        name = "%s %s" % (declared["package"], declared["version"])
        self.files.setdefault(name, path)
        self.recorded_version = name
        self.record_result = self._run([CATALOG, RECORD, str(path)])
        return self.record_result

    def record_again_first_file(self, package_version):
        """`fcon catalog record` of the file first recorded for that version."""
        self.record_result = self._run([CATALOG, RECORD, str(self.files[package_version])])
        return self.record_result

    def catalog_list(self):
        return self._run([CATALOG, LIST])

    def show(self, name):
        return self._run([SETTINGS, SHOW, name])

    def set(self, name, setting, value, reason=None):
        self.last_set = (name, SETTING_NAMES[setting], value)
        arguments = [SETTINGS, SET, name, SETTING_NAMES[setting], value]
        if reason is not None:
            arguments += [REASON_FLAG, reason]
        return self._run(arguments)

    def clear(self, name, setting):
        return self._run([SETTINGS, CLEAR, name, SETTING_NAMES[setting]])

    def settings_list(self):
        return self._run([SETTINGS, LIST])

    # -- reading what they printed -----------------------------------------

    def _rows(self, result, headings):
        """The rows under the line of headings, each a list of its columns."""
        lines = result.output.splitlines()
        for index, line in enumerate(lines):
            if tuple(COLUMNS.split(line.strip())[: len(headings)]) == headings:
                return [COLUMNS.split(row.strip()) for row in lines[index + 1 :] if row.strip()]
        return None

    def catalog_rows(self):
        """{name: (kind, package version)} of `fcon catalog list`, or None and why."""
        result = self.catalog_list()
        rows = self._rows(result, CATALOG_HEADINGS)
        if not result.ended_well() or rows is None:
            return None, repr(result)
        return {row[0]: (row[1], row[2] if len(row) > 2 else None) for row in rows}, repr(result)

    def lists_entries(self, expected, package_version):
        """Why `fcon catalog list` does not list each (kind, name) of
        `expected` from that package version, if it does not."""
        listed, shown = self.catalog_rows()
        if listed is None:
            return "the catalog could not be listed: %s" % shown
        wrong = [(kind, name) for kind, name in expected if listed.get(name) != (kind, package_version)]
        return ("not listed as %r from %s: %r\n%s" % (wrong, package_version, wrong, shown)) if wrong else None

    def lists_name(self, name):
        listed, shown = self.catalog_rows()
        if listed is None:
            raise AssertionError("the catalog could not be listed: %s" % shown)
        return name in listed, shown

    def setting_row(self, name, setting):
        """(value, set by) of the setting in `fcon settings show <name>`, or
        (None, None); and what was shown."""
        result = self.show(name)
        rows = self._rows(result, SHOW_HEADINGS)
        if not result.ended_well() or rows is None:
            raise AssertionError("the settings of %s could not be shown: %r" % (name, result))
        for row in rows:
            if row[0] == SETTING_NAMES[setting]:
                return (row[1] if len(row) > 1 else None), (row[2] if len(row) > 2 else None), repr(result)
        return None, None, repr(result)

    def shows_setting(self, name, setting, value, who):
        """Why the settings of `name` do not show that value set by that one, if they do not."""
        shown_value, set_by, shown = self.setting_row(name, setting)
        if (shown_value, set_by) != (value, SET_BY[who]):
            return "expected the %s %r set by %s, got %r set by %r\n%s" % (
                setting, value, SET_BY[who], shown_value, set_by, shown)  # fmt: skip
        return None

    def operator_values_shown(self, name):
        """The settings `fcon settings show <name>` says the operator set."""
        result = self.show(name)
        rows = self._rows(result, SHOW_HEADINGS)
        if not result.ended_well() or rows is None:
            raise AssertionError("the settings of %s could not be shown: %r" % (name, result))
        return [row[0] for row in rows if len(row) > 2 and row[2] == OPERATOR], repr(result)

    def operator_value_flagged(self, name, setting, value):
        """Why `fcon settings list` does not show that operator value flagged
        as no longer in the code, if it does not."""
        result = self.settings_list()
        rows = self._rows(result, LIST_HEADINGS)
        if not result.ended_well() or rows is None:
            return "the operator values could not be listed: %r" % result
        wanted = [name, SETTING_NAMES[setting], value, NO_LONGER_IN_THE_CODE]
        return None if wanted in rows else "no row %r\n%r" % (wanted, result)

    # -- what a command said -----------------------------------------------

    def _said(self, result, lines, exit_code):
        """Why `result` did not end with exit_code, saying each of `lines` as a line."""
        if result is None:
            return "no command was run"
        missing = [line for line in lines if line not in result.lines()]
        if result.timed_out or result.exit_code != exit_code or missing:
            return "expected exit %s and the lines %r; %r" % (exit_code, missing, result)
        return None

    def ended_well(self):
        """Why the latest command did not end well, if it did not."""
        return None if self.result.ended_well() else repr(self.result)

    def recording_refused_as_changed(self, package_version):
        return self._said(self.record_result, [ALREADY_RECORDED_OTHERWISE % package_version, NEVER_CHANGES],
                          REFUSED_EXIT)  # fmt: skip

    def recorded_already_unchanged(self, package_version):
        """Why recording the version's first file again is not told it is recorded already."""
        result = self.record_again_first_file(package_version)
        return self._said(result, [ALREADY_RECORDED % package_version], 0)

    def recording_warned(self, name, setting):
        setting_name = SETTING_NAMES[setting]
        return self._said(self.record_result, [NO_LONGER_HAS % (setting_name, name), CLEAR_IT % (name, setting_name)],
                          0)  # fmt: skip

    def refused_as_code_decided(self, name, setting):
        why = self._said(self.result, [DECIDED_BY_CODE % (setting, name)], REFUSED_EXIT)
        if why:
            return why
        named = [line for line in self.result.lines() if line.startswith(DATASET_SETTINGS)]
        listed = named[0][len(DATASET_SETTINGS) :].rstrip(".").split(", ") if named else []
        missing = [setting for setting in DATASET_SETTINGS_NAMED if setting not in listed]
        return ("the dataset's settings are not named (missing %r); %r" % (missing, self.result)) if missing else None

    def refused_as_not_a_look_back(self, value):
        return self._said(self.result, [NOT_A_LOOK_BACK % value, LOOK_BACK_IS], REFUSED_EXIT)

    def refused_for_no_reason(self, name):
        return self._said(self.result, ["error: " + NEEDS_A_REASON % name, SAY_WHY], REFUSED_EXIT)

    def refusal_text(self, name):
        """What a protected environment's refusal says, as its audit record holds it."""
        return NEEDS_A_REASON % name
