from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_personal_key_live_flow(monkeypatch):
    import src.models as models
    from src.pipeline import Pipeline

    calls = []
    monkeypatch.setenv("MODEL_A_PROVIDER", "openai")
    monkeypatch.setenv("MODEL_B_PROVIDER", "openai")
    monkeypatch.setenv("MODEL_FALLBACK_NAME", "")
    monkeypatch.setattr(models, "init_chat_model", lambda **kwargs: calls.append(kwargs) or object())
    original_process = Pipeline.process
    monkeypatch.setattr(Pipeline, "process", lambda self, row: original_process(Pipeline(demo=True), row))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90).run()
    app.sidebar.radio[0].set_value("Upload & Process").run()
    next(r for r in app.radio if r.label == "Processing mode").set_value("Live models").run()
    assert next(b for b in app.button if b.label == "Run classification").disabled
    key_input = next(t for t in app.text_input if t.label == "OpenAI API key")
    assert key_input.proto.type == key_input.proto.PASSWORD
    key_input.set_value("visitor-test-key").run()
    next(b for b in app.button if b.label == "Clear API key").click().run()
    assert next(t for t in app.text_input if t.label == "OpenAI API key").value == ""
    assert next(b for b in app.button if b.label == "Run classification").disabled
    next(t for t in app.text_input if t.label == "OpenAI API key").set_value("visitor-test-key").run()
    next(b for b in app.button if b.label == "Run classification").click().run(timeout=90)
    assert not app.exception
    assert len(calls) == 2
    assert all(c["api_key"].get_secret_value() == "visitor-test-key" for c in calls)
    assert len(app.session_state["results"]) == 440
    for field in ["results", "events", "run_meta"]:
        assert "visitor-test-key" not in str(app.session_state[field])
    second = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90).run()
    second.sidebar.radio[0].set_value("Upload & Process").run()
    next(r for r in second.radio if r.label == "Processing mode").set_value("Live models").run()
    assert next(t for t in second.text_input if t.label == "OpenAI API key").value == ""
    next(r for r in app.radio if r.label == "API credentials").set_value("Use server credentials").run()
    assert "personal_openai_key" not in app.session_state


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
