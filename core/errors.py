"""Errors shown to the person (card buttons, agent tools, CLI)."""


class ActionError(Exception):
    """A request that can't be done right now; the message says why."""


class StateError(ActionError):
    """A transition was attempted from the wrong state."""


class FinalError(Exception):
    """A stage failure that retrying won't fix (no API key, a draft that failed its checks twice).

    The stage fails at once with this message on the error card instead of using up its attempts.
    """


class Stopped(Exception):
    """The person stopped a Claude call partway (the Stop button): go back to the card, not to an error."""
