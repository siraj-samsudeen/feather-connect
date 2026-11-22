"""The store's own errors (design point 14): a database error never reaches
pages or the API raw. Each keeps the driver's error as its cause, for the log."""


class StoreError(Exception):
    """Any database error that has no meaning of its own here."""

    def __init__(self, message: str = "the database could not do this") -> None:
        super().__init__(message)


class AlreadyExistsError(StoreError):
    def __init__(self) -> None:
        super().__init__("already exists")


class ChangedBySomeoneElseError(StoreError):
    """The row is no longer at the version that was read."""

    def __init__(self) -> None:
        super().__init__("changed by someone else")


class NotFoundError(StoreError):
    def __init__(self) -> None:
        super().__init__("not found")


class BusyError(StoreError):
    """A deadlock or a serialization failure: the work can be run again."""

    def __init__(self) -> None:
        super().__init__("busy, try again")


class UnscopedQueryError(Exception):
    """A bug: SQL naming a table with a tenant, without the context's tenant."""
