from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_full_frontend_journey():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90).run()
    assert not app.exception
    assert app.metric[0].value == "1,000"
    app.sidebar.radio[0].set_value("Upload & Process").run()
    assert not app.exception
    next(b for b in app.button if b.label == "Run classification").click().run(timeout=90)
    assert not app.exception
    assert len(app.session_state["results"]) == 440
    for page in ["Insights", "Evaluation", "Run Cost", "Review Queue"]:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, page
    pending_before = sum(r["needs_review"] for r in app.session_state["results"])
    next(b for b in app.button if b.label == "Mark unclear").click().run()
    assert not app.exception
    assert sum(r["needs_review"] for r in app.session_state["results"]) == pending_before - 1
    app.sidebar.radio[0].set_value("Insights").run()
    assert not app.exception
