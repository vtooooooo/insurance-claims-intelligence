from streamlit.testing.v1 import AppTest

from src.generate import ROOT


def test_all_views_and_interactive_controls():
    app = AppTest.from_file(str(ROOT/"app/Home.py"),default_timeout=40).run()
    views = app.sidebar.radio[0].options
    assert len(views) == 8
    for view in views:
        app.sidebar.radio[0].set_value(view).run()
        assert not app.exception, (view,app.exception)
        assert app.title[0].value == view
    app.sidebar.radio[0].set_value("Claims Diagnostics").run()
    for item in app.selectbox[0].options:
        app.selectbox[0].set_value(item).run()
        assert not app.exception, (item,app.exception)
    app.sidebar.radio[0].set_value("Intervention Queue").run()
    app.sidebar.selectbox[0].set_value("Collision").run()
    app.slider[0].set_value(0).run()
    assert app.metric[0].value == "0"
    app.sidebar.radio[0].set_value("Intervention Simulator").run()
    assert app.dataframe[0].value.reviewed.max() > 0
    for preset in app.selectbox[0].options:
        app.selectbox[0].set_value(preset).run()
        assert not app.exception, (preset,app.exception)
    app.slider[0].set_value(0)
    app.button[0].click().run()
    assert not app.exception
    assert app.dataframe[0].value.reviewed.eq(0).all()
