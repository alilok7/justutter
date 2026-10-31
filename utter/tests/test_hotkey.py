from utter.hotkey import ChordState, key_matches


def press(state: ChordState, *names: str) -> list[str | None]:
    return [state.on_event(n, True) for n in names]


def release(state: ChordState, *names: str) -> list[str | None]:
    return [state.on_event(n, False) for n in names]


def test_key_matching() -> None:
    assert key_matches("ctrl", "ctrl")
    assert key_matches("ctrl", "right ctrl")
    assert key_matches("windows", "left windows")
    assert not key_matches("right ctrl", "left ctrl")
    assert not key_matches("ctrl", "alt")


def test_ctrl_then_win_starts_and_release_stops() -> None:
    s = ChordState(["ctrl", "windows"])
    assert press(s, "ctrl", "left windows") == [None, "start"]
    assert release(s, "left windows") == ["stop"]
    assert release(s, "ctrl") == [None]


def test_win_then_ctrl_also_starts() -> None:
    s = ChordState(["ctrl", "windows"])
    assert press(s, "left windows", "ctrl") == [None, "start"]
    assert release(s, "ctrl") == ["stop"]


def test_key_repeat_does_not_restart() -> None:
    s = ChordState(["ctrl", "windows"])
    press(s, "ctrl", "left windows")
    assert press(s, "ctrl", "left windows", "ctrl") == [None, None, None]


def test_third_key_cancels_windows_shortcut() -> None:
    s = ChordState(["ctrl", "windows"])
    press(s, "ctrl", "left windows")
    assert press(s, "right") == [None]
    release(s, "right")
    assert release(s, "left windows") == ["cancel"]


def test_other_key_held_first_prevents_start() -> None:
    s = ChordState(["ctrl", "windows"])
    assert press(s, "shift", "ctrl", "left windows") == [None, None, None]
    release(s, "shift", "ctrl", "left windows")
    assert press(s, "ctrl", "left windows") == [None, "start"]


def test_can_dictate_twice() -> None:
    s = ChordState(["ctrl", "windows"])
    press(s, "ctrl", "left windows")
    release(s, "left windows", "ctrl")
    assert press(s, "ctrl", "left windows") == [None, "start"]


def test_single_key_chord() -> None:
    s = ChordState(["right ctrl"])
    assert press(s, "ctrl") == [None]  # left/unspecified ctrl does not match "right ctrl"
    release(s, "ctrl")
    assert press(s, "right ctrl") == ["start"]
    assert release(s, "right ctrl") == ["stop"]
