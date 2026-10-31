def test_app_module_imports() -> None:
    """Catches syntax/import errors in the UI wiring, which unit tests don't otherwise load."""
    import utter.app
    import utter.ui

    assert callable(utter.app.main)
    assert utter.ui.Dashboard is not None
