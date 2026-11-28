"""The developer's terminal for stored data: `fcon data read`, `fcon data
versions` and `fcon data record` typed at a prompt, with a JSON-lines file of
orders written for the scenario, and what they printed (design decision 12 of
the stored-versions change). The commands, their flags, the file's shape and
every output line the steps rely on live here; the steps only ask questions.

Each command runs against the database of the product the scenario talks to
(the run's), with only that address as its setting. The scenario's dataset is
put into that database's catalog directly (support/catalog.py): the one thing
the product cannot yet be made to do from outside.
"""

import os
import re
import tempfile
from datetime import datetime

from pages.database_commands import TRACEBACK, Result
from support import catalog, stack

DATA = "data"
READ = "read"
VERSIONS = "versions"
RECORD = "record"
KEY_FLAG = "--key"
BY_FLAG = "--by"
TIME_ZONE_FLAG = "--time-zone"
COMPLETE_FLAG = "--complete"
SLICE_FLAG = "--slice"
ALLOW_EMPTY_FLAG = "--allow-empty"
RECORDS_FLAG = "--records"
AS_OF_FLAG = "--as-of"
DATABASE_SETTING = "FCON_DATABASE_URL"
# The suite reads a command's output as UTF-8 (slice names hold a "·"), so the
# pipe is UTF-8 on every system, Windows included.
PIPE_ENCODING = {"PYTHONIOENCODING": "utf-8"}

# The scenarios' dataset: orders, keyed by their number, split by shop and by
# the day they were ordered on, in UTC.
KEY = "order_id"
SCHEME = "shop,day:ordered_at"
TIME_ZONE = "UTC"
DEFAULT_AMOUNT = "10.00"
CHANGED_AMOUNT = "11.00"  # an amount that differs from the default
ORDER_TIME = "09:%02d:00Z"  # an order's time of day; the minute keeps orders apart

# -- the output lines of decision 12 ----------------------------------------

_COUNTS = r"(\d+) read, (\d+) added, (\d+) changed, (\d+) deleted, (\d+) unchanged"
SEALED = re.compile(r'^sealed version (\d+) of "(.+)" \(commit (\d+), ([^)]+)\): ' + _COUNTS + "$")
NOTHING_CHANGED = re.compile(r'^nothing changed in "(.+)": (\d+) read, (\d+) unchanged; no version stored$')
VERSION_LINE = re.compile(r"^  version (\d+)\s+commit (\d+)\s+(.+?)\s+" + _COUNTS + "$")
NO_VERSIONS = "  no versions"
RECORD_LINE = re.compile(r"^    (\S+) (added|changed|deleted)$")
COMPLETE = "complete"
RECORD_HEADER = re.compile(r"^record (\S+)$")
SLICE_LINE = re.compile(r"^slice: (.+)$")
LAST_CHANGED = re.compile(r"^last changed by: version (\d+) \(commit (\d+)\)$")
AT_SOURCE = re.compile(r"^at the source: (present|removed)$")
FIELD_LINE = re.compile(r"^  ([^:\s]+): (.*)$")
REMOVED = "removed"
ERROR_PREFIX = "error:"
WOULD_EMPTY = "empt"  # the refusal says the slice would be emptied (empty, emptied)


def day_of(text):
    """A date from a scenario's words, such as '18 Oct 2026'."""
    return datetime.strptime(text, "%d %b %Y").date()


def slice_name(shop, day):
    """The business name of one shop's orders of one day: 'Shop 12 · 18 Oct 2026'."""
    return "Shop %d · %d %s" % (shop, day.day, day.strftime("%b %Y"))


def slice_values(shop, day):
    """The same slice as `--slice` names it: 'shop=12,day=2026-10-18'."""
    return "shop=%d,day=%s" % (shop, day.isoformat())


class Order:
    """One order as the scenario's source returns it."""

    def __init__(self, order_id, shop, day, amount=DEFAULT_AMOUNT):
        self.order_id = order_id
        self.shop = shop
        self.day = day
        self.amount = amount

    def copy(self, **changes):
        order = Order(self.order_id, self.shop, self.day, self.amount)
        for name, value in changes.items():
            setattr(order, name, value)
        return order

    def json_line(self):
        """The order as one JSON object, its amount a number with two decimals
        (written by hand: json.dumps would print 10.00 as 10.0)."""
        ordered_at = "%sT%s" % (self.day.isoformat(), ORDER_TIME % (self.order_id % 60))
        return '{"order_id": %d, "shop": %d, "ordered_at": "%s", "amount": %s}' % (
            self.order_id, self.shop, ordered_at, self.amount,
        )  # fmt: skip


class Version:
    """One sealed version of a slice, as `fcon data versions` lists it."""

    def __init__(self, number, commit, kind, counts):
        self.number = number
        self.commit = commit
        self.kind = kind
        self.counts = counts  # (read, added, changed, deleted, unchanged)
        self.records = []  # (key, how), with --records

    def record_keys(self):
        return [key for key, _ in self.records]

    def __repr__(self):
        return "version %d (commit %d, %s): %r %r" % (self.number, self.commit, self.kind, self.counts, self.records)


class FollowedRecord:
    """One record as `fcon data record` shows it."""

    def __init__(self, key):
        self.key = key
        self.slice = None
        self.last_changed_by = None  # (version, commit), now only
        self.at_source = None  # 'present' or 'removed'
        self.fields = {}  # name -> the text shown


class DataCommands:
    def __init__(self, world):
        self.world = world
        self.dataset = None  # the scenario's dataset, by full name
        self.allows_empty = False
        self.orders = {}  # order_id -> the order as last read
        self.read_slice = None  # (shop, day) of the scenario's reads
        self.named_slice = None  # the slice a step named last
        self.result = None
        self.followed = None  # the record followed last
        self.results = []

    # -- the dataset -----------------------------------------------------

    def give_dataset(self, allows_empty=False):
        """As setup: a dataset of orders of the scenario's own, in the catalog."""
        self.dataset = catalog.add_dataset(self.world.product_database_url())
        self.allows_empty = allows_empty
        self.world.screen.note("a dataset %s in the catalog (as setup)" % self.dataset)

    def _dataset(self):
        if self.dataset is None:
            raise AssertionError("the scenario has no dataset yet")
        return self.dataset

    # -- running a command -----------------------------------------------

    def _run(self, arguments):
        settings = {DATABASE_SETTING: self.world.product_database_url(), **PIPE_ENCODING}
        code, out, err, timed_out = stack.finish_fcon(stack.start_fcon([DATA, *arguments], settings))
        result = Result(" ".join([DATA, *arguments]), code, out, err, timed_out)
        self.world.screen.command("fcon " + result.command, out + err, code)
        self.results.append(result)
        self.result = result
        return result

    def _read_file(self, orders, extra=()):
        """`fcon data read` of a JSON-lines file holding `orders`, in order."""
        handle, path = tempfile.mkstemp(prefix="fcon-orders-", suffix=".jsonl")
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as file:
                file.writelines(order.json_line() + "\n" for order in orders)
            arguments = [READ, self._dataset(), path, KEY_FLAG, KEY, BY_FLAG, SCHEME, TIME_ZONE_FLAG, TIME_ZONE]
            result = self._run([*arguments, *extra])
        finally:
            os.remove(path)
        if result.ended_well():
            for order in orders:
                self.orders[order.order_id] = order
        return result

    @staticmethod
    def _as_setup(result):
        if not result.ended_well():
            raise AssertionError("the read did not end well; %r" % result)
        return result

    # -- reads -------------------------------------------------------------

    def read_orders(self, ids, shop, day, amount=DEFAULT_AMOUNT, setup=False):
        """A changes-only read of those orders of one shop and day."""
        self.read_slice = (shop, day)
        result = self._read_file([Order(order_id, shop, day, amount) for order_id in ids])
        return self._as_setup(result) if setup else result

    def _known(self, order_id):
        if order_id not in self.orders:
            raise AssertionError("the scenario has not read order %d yet" % order_id)
        return self.orders[order_id]

    def read_again(self, changed=None, amount=CHANGED_AMOUNT, setup=False):
        """Every order read so far, again; the one `changed` with another amount."""
        orders = [
            order.copy(amount=amount) if order.order_id == changed else order
            for order in sorted(self.orders.values(), key=lambda order: order.order_id)
        ]  # fmt: skip
        result = self._read_file(orders)
        return self._as_setup(result) if setup else result

    def read_one_again(self, order_id, amount=None, day=None, setup=False):
        """One order read so far, alone, with a new amount or day."""
        order = self._known(order_id)
        changes = {name: value for name, value in (("amount", amount), ("day", day)) if value is not None}
        result = self._read_file([order.copy(**changes)])
        return self._as_setup(result) if setup else result

    def read_twice_in_one_read(self, order_id, shop, day, first, second):
        """One read holding the same order twice, with two amounts."""
        self.read_slice = (shop, day)
        return self._read_file([Order(order_id, shop, day, first), Order(order_id, shop, day, second)])

    def read_slice_in_full(self, ids):
        """A complete read of the scenario's slice, returning only those orders."""
        if self.read_slice is None:
            raise AssertionError("the scenario has read no slice yet")
        extra = [COMPLETE_FLAG, SLICE_FLAG, slice_values(*self.read_slice)]
        if self.allows_empty:
            extra.append(ALLOW_EMPTY_FLAG)
        return self._read_file([self._known(order_id) for order_id in ids], extra)

    # -- versions ----------------------------------------------------------

    def name_slice(self, name):
        """The slice later steps mean by 'its' and 'version N'."""
        self.named_slice = name

    def _slice(self):
        if self.named_slice is not None:
            return self.named_slice
        if self.read_slice is not None:
            return slice_name(*self.read_slice)
        raise AssertionError("no slice has been named or read yet")

    def versions(self, name=None):
        """The sealed versions of a slice (the one meant now, when no name), with their records."""
        name = name or self._slice()
        result = self._run([VERSIONS, self._dataset(), RECORDS_FLAG])
        if not result.ended_well():
            raise AssertionError("`fcon data versions` did not end well; %r" % result)
        slices = {}
        current = None
        for line in result.output.splitlines():
            if not line.strip():
                continue
            version = VERSION_LINE.match(line)
            record = RECORD_LINE.match(line)
            if version and current is not None:
                number, commit, kind, *counts = version.groups()
                slices[current].append(Version(int(number), int(commit), kind, tuple(int(n) for n in counts)))
            elif record and current is not None and slices[current]:
                slices[current][-1].records.append(record.groups())
            elif line == NO_VERSIONS and current is not None:
                continue
            elif not line.startswith(" "):
                current = line.strip()
                slices.setdefault(current, [])
            else:
                raise AssertionError("cannot read the line %r of `fcon data versions`; %r" % (line, result))
        return slices.get(name, []), result

    def version(self, number):
        """(version, why): that version of the slice meant now."""
        found, result = self.versions()
        by_number = {version.number: version for version in found}
        if number not in by_number:
            raise AssertionError("%r has no version %d; %r" % (self._slice(), number, result))
        return by_number[number], result

    # -- following a record ------------------------------------------------

    def follow(self, order_id, as_of=None):
        """`fcon data record` of that order (as of a commit, when given), read."""
        arguments = [RECORD, self._dataset(), str(order_id)]
        if as_of is not None:
            arguments += [AS_OF_FLAG, str(as_of)]
        result = self._run(arguments)
        if not result.ended_well():
            raise AssertionError("`fcon data record` did not end well; %r" % result)
        followed = None
        for line in result.output.splitlines():
            header = RECORD_HEADER.match(line)
            if header:
                followed = FollowedRecord(header.group(1))
                continue
            if followed is None or not line.strip():
                continue
            if found := SLICE_LINE.match(line):
                followed.slice = found.group(1)
            elif found := LAST_CHANGED.match(line):
                followed.last_changed_by = (int(found.group(1)), int(found.group(2)))
            elif found := AT_SOURCE.match(line):
                followed.at_source = found.group(1)
            elif found := FIELD_LINE.match(line):
                followed.fields[found.group(1)] = found.group(2)
        if followed is None or followed.key != str(order_id):
            raise AssertionError("`fcon data record` showed no record %d; %r" % (order_id, result))
        self.followed = (followed, result)
        return self.followed

    def _followed(self):
        if self.followed is None:
            raise AssertionError("no record has been followed yet")
        return self.followed

    def shows_amount(self, amount):
        """(yes?, why): the record followed last shows that amount."""
        followed, result = self._followed()
        return followed.fields.get("amount") == amount, "amount %r; %r" % (followed.fields.get("amount"), result)

    def shows_slice(self, name):
        followed, result = self._followed()
        return followed.slice == name, "slice %r; %r" % (followed.slice, result)

    def removed_at_source(self):
        followed, result = self._followed()
        return followed.at_source == REMOVED, "at the source: %r; %r" % (followed.at_source, result)

    def last_changed_by(self, number):
        followed, result = self._followed()
        changed = followed.last_changed_by
        return changed is not None and changed[0] == number, "last changed by %r; %r" % (changed, result)

    # -- what a read said --------------------------------------------------

    def told_nothing_changed(self):
        """(yes?, why): the last read ended well, saying nothing changed in the scenario's slice."""
        result = self.result
        if result is None:
            return False, "no `fcon data` command has been run yet"
        name = slice_name(*self.read_slice)
        said = [found.group(1) for found in map(NOTHING_CHANGED.match, result.output.splitlines()) if found]
        sealed = [line for line in result.output.splitlines() if SEALED.match(line)]
        ok = result.ended_well() and name in said and not sealed
        return ok, "expected: nothing changed in %r, no version sealed; %r" % (name, result)

    def refused_would_empty(self):
        """(yes?, why): the last read was refused, an error line saying the
        scenario's slice would be emptied, with no stack trace."""
        result = self.result
        if result is None:
            return False, "no `fcon data` command has been run yet"
        name = slice_name(*self.read_slice)
        text = result.output + result.errors
        errors = [line for line in result.lines() if line.startswith(ERROR_PREFIX)]
        ok = (
            not result.timed_out
            and result.exit_code != 0
            and TRACEBACK not in text
            and name in text
            and any(WOULD_EMPTY in line for line in errors)
        )
        return ok, "expected a refusal naming %r as emptied; %r" % (name, result)
