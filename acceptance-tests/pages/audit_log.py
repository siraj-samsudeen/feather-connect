"""The audit log, as an auditor reads it in the product's database: the
records of sign-ins and what else a scenario did. The table, its fields, the
values the product writes and the address the browsers come from live here;
the steps only ask questions.

A sign-in attempt is a row the store adds, so its audit record is an
`insert` into `fcon.sign_in_attempt` whose `after` holds the name tried, the
visitor's address and the outcome (design, decision 3; point 8). The run's
database serves every scenario and its audit is never emptied, so only the
records written since the scenario began are read there (World.audit_mark);
a database of the scenario's own is read whole.

A setting an operator sets is an `insert` (the first time) or `update` of
`fcon.operator_setting`, its `after` holding the setting and the value, by
`system:cli` from the command line, with the reason given; a change a
protected environment refuses is a `refused` record of that table whose
`row_key` is the entry's name and the setting, and whose reason is the refusal.
"""

import json

from support import run_database

ATTEMPT_TABLE = "fcon.sign_in_attempt"
INSERT = "insert"
REFUSED = "refused"
SUCCEEDED = "succeeded"
SETTING_TABLE = "fcon.operator_setting"
SETTING_CHANGES = ("insert", "update")
BY_THE_COMMAND_LINE = "system:cli"
# Every browser of the run is on this machine and talks to 127.0.0.1.
USER_ADDRESS = "127.0.0.1"
# The fields of a record a password could hide in.
TEXT_FIELDS = ("row_key", "before", "after", "reason")


class AuditLog:
    def __init__(self, world):
        self.world = world

    def records(self):
        """The scenario's audit records, oldest first, each a dict of the
        audit table's columns."""
        reader = self.world.audit_reader
        if reader is not None:
            return reader(run_database.AUDIT_QUERY_ALL)
        if self.world.scenario_database is not None:
            return run_database.audit_records(None, self.world.scenario_database)
        return run_database.audit_records(self.world.audit_mark)

    def _show(self, records):
        return "the scenario's audit records:\n  %s" % "\n  ".join(
            "%s %s %s after=%s reason=%s" % (r.get("table_name"), r.get("action"), r.get("created_by"),
                                             json.dumps(r.get("after")), r.get("reason"))
            for r in records
        ) if records else "the scenario wrote no audit record"  # fmt: skip

    def sign_ins(self, name, records=None):
        """The `after` of each recorded sign-in attempt for `name`, oldest first."""
        records = self.records() if records is None else records
        return [
            r["after"] for r in records
            if r.get("table_name") == ATTEMPT_TABLE and r.get("action") == INSERT
            and isinstance(r.get("after"), dict) and r["after"].get("name") == name
        ]  # fmt: skip

    def refused_and_successful_sign_in_problems(self, name, address=USER_ADDRESS):
        """Why the log does not hold, for `name`, a refused and then a
        successful sign-in attempt, both from `address`."""
        records = self.records()
        attempts = self.sign_ins(name, records)
        outcomes = [a.get("outcome") for a in attempts]
        problems = []
        for outcome in (REFUSED, SUCCEEDED):
            if outcome not in outcomes:
                problems.append("no %s sign-in for %r is recorded" % (outcome, name))
        wrong = [a for a in attempts if a.get("address") != address]
        if wrong:
            problems.append("%d sign-in(s) for %r are recorded from another address than %s: %r"
                            % (len(wrong), name, address, wrong))  # fmt: skip
        if REFUSED in outcomes and SUCCEEDED in outcomes and outcomes.index(REFUSED) > outcomes.index(SUCCEEDED):
            problems.append("the refused sign-in is recorded after the successful one")
        if problems:
            problems.append(self._show(records))
        return problems

    def successful_sign_in_address(self, name):
        """(the address of the last successful sign-in recorded for `name`, or
        None, what the log holds)."""
        records = self.records()
        good = [a for a in self.sign_ins(name, records) if a.get("outcome") == SUCCEEDED]
        return (good[-1].get("address") if good else None), self._show(records)

    def password_problems(self, passwords):
        """Which of `passwords` appear in any record of the scenario, in any field."""
        if not passwords:
            return ["the scenario typed no password to look for"]
        records = self.records()
        if not records:
            return [self._show(records)]
        problems = []
        for password in sorted(set(passwords)):
            for record in records:
                text = json.dumps([record.get(field) for field in TEXT_FIELDS])
                if password in text:
                    problems.append("a password appears in the %s %s record by %s"
                                    % (record.get("table_name"), record.get("action"), record.get("created_by")))  # fmt: skip
        return problems

    def setting_change_problems(self, setting, value, reason):
        """Why the log does not hold a change of `setting` to `value` by the
        command line, with `reason`, if it does not."""
        records = self.records()
        changes = [
            r for r in records
            if r.get("table_name") == SETTING_TABLE and r.get("action") in SETTING_CHANGES
            and isinstance(r.get("after"), dict)
            and r["after"].get("setting") == setting and r["after"].get("value") == value
        ]  # fmt: skip
        good = [r for r in changes if r.get("created_by") == BY_THE_COMMAND_LINE and r.get("reason") == reason]
        return None if good else "no change of the %s to %r by %s with the reason %r; %s" % (
            setting, value, BY_THE_COMMAND_LINE, reason, self._show(records))  # fmt: skip

    def setting_refusal_problems(self, name, setting, refusal):
        """Why the log does not hold a refused change of `setting` of `name`,
        by the command line, whose reason holds `refusal`, if it does not."""
        records = self.records()
        refused = [
            r for r in records
            if r.get("table_name") == SETTING_TABLE and r.get("action") == REFUSED
            and r.get("row_key") == "%s/%s" % (name, setting) and r.get("created_by") == BY_THE_COMMAND_LINE
            and refusal in (r.get("reason") or "")
        ]  # fmt: skip
        return None if refused else "no refused change of the %s of %s saying %r; %s" % (
            setting, name, refusal, self._show(records))  # fmt: skip
