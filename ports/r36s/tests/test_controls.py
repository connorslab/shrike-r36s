import math
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from controls import Controls, ROWS, SHIFTED, viewport


def active():
    state = Controls()
    state.help = False
    return state


def test_help_dismiss_does_not_click_wallet():
    state = Controls()
    assert state.event(1, 304, 1) == []
    assert not state.help


def test_click_and_drag_lifecycle():
    state = active()
    assert state.event(1, 304, 1) == [("button_down", 1)]
    state.event(3, 16, 1)
    assert state.tick(0.02)[0][0] == "move"
    assert state.event(1, 304, 0) == [("button_up", 1)]


def test_overflow_releases_mouse_and_stops_pointer():
    state = active()
    state.event(1, 304, 1)
    state.event(3, 16, 1)
    assert state.event(0, 3, 0) == [("release_all", None)]
    assert state.tick(0.05) == []


@pytest.mark.parametrize("buttons", [(314, 315), (315, 314)])
def test_close_chord_does_not_send_escape_or_toggle_help(buttons):
    state = active()
    assert state.event(1, buttons[0], 1) == []
    assert state.event(1, buttons[1], 1) == [("close_window", None)]
    assert state.event(1, buttons[0], 0) == []
    assert state.event(1, buttons[1], 0) == []
    assert not state.help


def test_start_escape_on_release():
    state = active()
    assert state.event(1, 315, 1) == []
    assert state.event(1, 315, 0) == [("key", "Escape")]


def test_pointer_clamps_at_all_edges():
    state = active()
    for direction, expected in [(-1, (0, 0)), (1, (1279, 959))]:
        state.event(3, 16, direction)
        state.event(3, 17, direction)
        for _ in range(100):
            state.tick(0.1)
        assert (state.x, state.y) == expected


def test_precision_mode_moves_more_slowly():
    fast, slow = active(), active()
    for state in (fast, slow):
        state.event(3, 16, 1)
    slow.event(1, 313, 1)
    fast.tick(0.1)
    slow.tick(0.1)
    assert slow.x < fast.x


def test_diagonal_does_not_move_faster():
    straight, diagonal = active(), active()
    straight.event(3, 16, 1)
    diagonal.event(3, 16, 1)
    diagonal.event(3, 17, 1)
    straight.tick(0.1)
    diagonal.tick(0.1)
    assert straight.x - 640 == pytest.approx(math.hypot(diagonal.x - 640, diagonal.y - 480))


def test_keyboard_navigation_never_moves_pointer():
    state = active()
    assert state.event(1, 308, 1) == [("release_all", None)]
    state.event(3, 16, 1)
    state.tick(0.02)
    assert state.col == 1 and state.x == 640
    assert state.event(1, 304, 1) == [("text", "2")]


@pytest.mark.parametrize("key,expected", [("Space", "space"), ("Backspace", "BackSpace"), ("Tab", "Tab"), ("Enter", "Return")])
def test_keyboard_special_keys(key, expected):
    state = active()
    state.keyboard = True
    state.row, state.col = 4, ROWS[4].index(key)
    assert state.activate_key() == [("key", expected)]


def test_keyboard_shift_and_punctuation():
    state = active()
    state.shift = True
    assert state.label("a") == "A"
    assert state.label("1") == "!"
    assert state.label(";") == ":"
    assert state.label("/") == "?"
    assert state.label("\\") == "|"
    assert state.label(",") == "<"
    assert state.label(".") == ">"


def test_keyboard_can_type_all_printable_ascii():
    state = active()
    available = {" "}
    for shift in (False, True):
        state.shift = shift
        available.update(state.label(k) for row in ROWS for k in row if len(k) == 1)
    assert available == {chr(n) for n in range(32, 127)}


def test_zoom_viewport_stays_within_virtual_screen():
    state = active()
    assert viewport(state, 640, 480) == (0, 0, 1280, 960)
    state.zoom = True
    state.x = state.y = 0
    assert viewport(state, 640, 480) == (0, 0, 640, 480)
    state.x, state.y = 1279, 959
    assert viewport(state, 640, 480) == (640, 480, 1280, 960)


def test_custom_face_button_mapping():
    state = Controls(mapping={305: "click"})
    state.help = False
    assert state.event(1, 305, 1) == [("button_down", 1)]


def test_kernel_repeat_does_not_retoggle_keyboard():
    state = active()
    state.event(1, 308, 1)
    state.event(1, 308, 2)
    assert state.keyboard


def test_select_toggles_help_without_sending_wallet_key():
    state = active()
    assert state.event(1, 314, 1) == []
    assert state.event(1, 314, 0) == []
    assert state.help
