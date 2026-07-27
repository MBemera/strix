"""Regression tests for the TUI's app-lifecycle guards.

``StrixTUIApp`` subclasses ``textual.app.App``, whose ``is_mounted`` is a
*method* taking a widget — not the ``Widget.is_mounted`` property. A bare
``self.is_mounted`` on the app is therefore a bound method object, which is
always truthy, so ``if not self.is_mounted: return`` never returns. The
app-level guards need ``App.is_running`` to detect a stopped app.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import cast

from textual.app import App
from textual.widget import Widget

from strix.interface.tui import app as tui_app


# App-level guards converted from the always-truthy self.is_mounted.
_CONVERTED_GUARDS = 13


class StoppedTuiState:
    show_splash = False
    is_running = False

    def __init__(self) -> None:
        self.query_count = 0

    def is_mounted(self, _widget: object) -> bool:
        return False

    def query_one(self, *_args: object, **_kwargs: object) -> None:
        self.query_count += 1
        raise ValueError("the TUI is not mounted")


def test_app_is_mounted_is_a_method_that_needs_a_widget() -> None:
    """The API shape that caused the bug: truthy when read without calling it."""
    assert inspect.isfunction(inspect.getattr_static(App, "is_mounted"))
    assert "widget" in inspect.signature(App.is_mounted).parameters
    assert bool(App().is_mounted) is True


def test_widget_is_mounted_is_a_property() -> None:
    """``Widget.is_mounted`` *is* a property — the source of the confusion."""
    assert isinstance(inspect.getattr_static(Widget, "is_mounted"), property)


def test_app_is_running_is_a_property() -> None:
    assert isinstance(inspect.getattr_static(App, "is_running"), property)


def test_tui_app_never_reads_is_mounted_off_itself() -> None:
    """``self.is_mounted`` in the TUI is always a bug; widget access is fine."""
    source = Path(str(tui_app.__file__)).read_text(encoding="utf-8")
    offenders = [
        f"{number}: {line.strip()}"
        for number, line in enumerate(source.splitlines(), start=1)
        if "self.is_mounted" in line
    ]

    assert not offenders, "self.is_mounted is always truthy; use self.is_running:\n" + "\n".join(
        offenders
    )
    # A floor, not an exact count: new guards are welcome, silent removal is not.
    assert source.count("self.is_running") >= _CONVERTED_GUARDS


def test_real_tui_action_returns_before_query_when_app_is_stopped() -> None:
    stopped_tui_state = StoppedTuiState()

    tui_app.StrixTUIApp.action_toggle_help(cast("tui_app.StrixTUIApp", stopped_tui_state))

    assert stopped_tui_state.query_count == 0
