import os
import time
from datetime import datetime
from types import SimpleNamespace
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from utter.config import Mode, Settings  # noqa: E402
from utter.history import Dictation, History, Stats  # noqa: E402
from utter.personal import PersonalMemory  # noqa: E402
from utter.ui import Dashboard, FloatingBar, Tray, logo_pixmap, make_app  # noqa: E402


@pytest.fixture(scope="module")
def qt() -> QApplication:
    return make_app()


def pump(ms: int) -> None:
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.01)


def test_bar_hidden_until_set_and_fades_out(qt: QApplication) -> None:
    bar = FloatingBar(lambda: 0.05)
    assert not bar.isVisible()
    bar.set("listening", "Listening", "Esc cancel")
    pump(200)
    assert bar.isVisible() and bar.state == "listening"
    assert bar.windowOpacity() > 0.9
    bar.set("ready", "")
    pump(450)
    assert not bar.isVisible()


def test_bar_reverts_after_timeout(qt: QApplication) -> None:
    bar = FloatingBar()
    bar.set("done", "Inserted", "email · 1.8s", revert_ms=100)
    pump(150)
    assert bar.isVisible()
    pump(500)
    assert not bar.isVisible()


def test_bar_width_hugs_content(qt: QApplication) -> None:
    bar = FloatingBar()
    bar.set("warn", "Too short")
    short = bar.width()
    bar.set("warn", "Too short", "hold the keys while you speak")
    assert bar.width() > short
    bar.set("ready", "")


def test_handsfree_timer_counts(qt: QApplication) -> None:
    bar = FloatingBar()
    bar.set("handsfree", "0:00", "Ctrl+Win to finish")
    bar._started -= 65
    pump(100)
    assert bar.text == "1:05"
    bar.set("ready", "")


@pytest.mark.parametrize("state", ["listening", "handsfree", "working", "done", "warn",
                                   "error", "cancelled", "paused"])
def test_every_state_paints(qt: QApplication, state: str) -> None:
    bar = FloatingBar(lambda: 0.1)
    bar.set(state, "Label", "detail")
    image = bar.grab()
    assert not image.isNull()
    bar.set("ready", "")


def test_logo_renders(qt: QApplication) -> None:
    assert not logo_pixmap(64).isNull()


def fake_app() -> Any:
    calls: dict[str, list[Any]] = {"polish": [], "learn": [], "paused": [], "added": []}
    history = History()
    history.add(Dictation(at=datetime.now(), app="outlook.exe", mode=Mode.EMAIL,
                          raw="hi professor tan", clean="Hi Professor Tan.",
                          rules=["mode email: added final period"], latency_s=1.8,
                          action="pasted"))
    stats = Stats()
    stats.record(2431, 1.9)
    return SimpleNamespace(
        settings=Settings(), stats=stats, history=history, guard=SimpleNamespace(blocked_count=0),
        polisher=SimpleNamespace(model="qwen2.5:1.5b"), polisher_ready=True,
        model_name="small.en", memory=PersonalMemory(vocab={"MERaLiON": 3}),
        config_dir=".", calls=calls,
        set_polish=lambda v: calls["polish"].append(v),
        set_learning=lambda v: calls["learn"].append(v),
        set_paused=lambda v: calls["paused"].append(v),
        add_glossary=lambda h, w: calls["added"].append((h, w)),
        remove_glossary=lambda i: None, forget_memory=lambda: None,
        quit=lambda: None, toggle_dashboard=lambda: None,
    )


def test_dashboard_pages_render(qt: QApplication) -> None:
    app = fake_app()
    dash = Dashboard(app)
    dash.show()
    for row in range(len(Dashboard.PAGES)):
        dash.nav.setCurrentRow(row)
        pump(20)
        assert dash.stack.currentIndex() == row
    dash.nav.setCurrentRow(0)
    dash.refresh_home()
    assert "Network requests: 0" in dash.badge.text()
    assert dash.words_value.text() == "2,431"
    assert "431 over" in dash.words_note.text()
    assert dash.recent.count() == 1
    dash.nav.setCurrentRow(2)
    assert dash.gloss.rowCount() == len(app.settings.glossary)
    dash.heard_in.setText("ptero")
    dash.written_in.setText("Pterodactylus")
    dash._add_gloss()
    assert app.calls["added"] == [("ptero", "Pterodactylus")]
    dash.polish_toggle.click()
    assert app.calls["polish"] == [False]
    dash.hide()


def test_tray_pause_toggles_app(qt: QApplication) -> None:
    app = fake_app()
    tray = Tray(app)
    tray.pause_action.setChecked(True)
    assert app.calls["paused"] == [True]
    assert "paused" in tray.status.text()
