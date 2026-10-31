from utter.hotkey import ChordState, key_matches


def press(state: ChordState, *names: str, now: float = 0.0) -> list[str | None]:
    return [state.on_event(n, True, now) for n in names]


def release(state: ChordState, *names: str, now: float = 0.0) -> list[str | None]:
    return [state.on_event(n, False, now) for n in names]


def chord() -> ChordState:
    return ChordState(["ctrl", "windows"])


def test_key_matching() -> None:
    assert key_matches("ctrl", "ctrl")
    assert key_matches("ctrl", "right ctrl")
    assert key_matches("windows", "left windows")
    assert not key_matches("right ctrl", "left ctrl")
    assert not key_matches("ctrl", "alt")


def test_ctrl_then_win_starts_and_release_stops() -> None:
    s = chord()
    assert press(s, "ctrl", "left windows") == [None, "start"]
    assert release(s, "left windows") == ["stop"]
    assert release(s, "ctrl") == [None]


def test_win_then_ctrl_also_starts() -> None:
    s = chord()
    assert press(s, "left windows", "ctrl") == [None, "start"]
    assert release(s, "ctrl") == ["stop"]


def test_key_repeat_does_not_restart() -> None:
    s = chord()
    press(s, "ctrl", "left windows")
    assert press(s, "ctrl", "left windows", "ctrl") == [None, None, None]


def test_other_keys_during_hold_keep_recording() -> None:
    s = chord()
    press(s, "ctrl", "left windows")
    assert press(s, "right", "a", "tab") == [None, None, None]
    assert s.mode == "hold"
    release(s, "right", "a", "tab")
    assert release(s, "left windows") == ["stop"]


def test_escape_cancels_a_hold() -> None:
    s = chord()
    press(s, "ctrl", "left windows")
    assert press(s, "esc") == ["cancel"]
    assert s.cancel_reason == "Esc"
    release(s, "esc", "left windows", "ctrl")
    assert press(s, "ctrl", "left windows") == [None, "start"]


def test_other_key_held_first_prevents_start() -> None:
    s = chord()
    assert press(s, "shift", "ctrl", "left windows") == [None, None, None]
    release(s, "shift", "ctrl", "left windows")
    assert press(s, "ctrl", "left windows") == [None, "start"]


def test_stale_other_key_does_not_block_forever() -> None:
    s = chord()
    press(s, "alt", now=0.0)  # its key-up was lost (e.g. alt-tab into an admin window)
    assert press(s, "ctrl", "left windows", now=30.0) == [None, "start"]


def test_can_dictate_twice() -> None:
    s = chord()
    press(s, "ctrl", "left windows")
    release(s, "left windows", "ctrl")
    assert press(s, "ctrl", "left windows") == [None, "start"]


def test_space_switches_to_handsfree_and_release_keeps_recording() -> None:
    s = chord()
    assert press(s, "ctrl", "left windows", "space") == [None, "start", "handsfree"]
    assert release(s, "space", "left windows", "ctrl") == [None, None, None]
    assert s.mode == "handsfree"


def test_handsfree_finishes_on_next_chord_press() -> None:
    s = chord()
    press(s, "ctrl", "left windows", "space")
    release(s, "space", "left windows", "ctrl")
    assert press(s, "ctrl", "left windows") == [None, "stop"]
    assert s.mode == "idle"
    assert release(s, "left windows", "ctrl") == [None, None]
    assert press(s, "ctrl", "left windows") == [None, "start"]  # usable again afterwards


def test_handsfree_ignores_chord_until_released_once() -> None:
    s = chord()
    press(s, "ctrl", "left windows", "space")
    release(s, "space")
    assert press(s, "ctrl", "left windows") == [None, None]  # still held: auto-repeat, not finish
    assert s.mode == "handsfree"


def test_handsfree_escape_cancels() -> None:
    s = chord()
    press(s, "ctrl", "left windows", "space")
    release(s, "space", "left windows", "ctrl")
    assert press(s, "esc") == ["cancel"]
    assert s.cancel_reason == "Esc"
    assert s.mode == "idle"


def test_handsfree_typing_other_keys_is_ignored() -> None:
    s = chord()
    press(s, "ctrl", "left windows", "space")
    release(s, "space", "left windows", "ctrl")
    assert press(s, "a", "b") == [None, None]
    assert s.mode == "handsfree"


def test_force_stop_from_watchdog() -> None:
    s = chord()
    press(s, "ctrl", "left windows")
    assert s.force_stop() == "stop"
    assert s.mode == "idle"
    assert s.force_stop() is None


def test_single_key_chord() -> None:
    s = ChordState(["right ctrl"])
    assert press(s, "ctrl") == [None]  # left/unspecified ctrl does not match "right ctrl"
    release(s, "ctrl")
    assert press(s, "right ctrl") == ["start"]
    assert release(s, "right ctrl") == ["stop"]
