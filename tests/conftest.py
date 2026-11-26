"""Test settings for both modules.

The servers' run tokens (rewrite stages 1-2, 26-Nov-2026): in the app each module makes its own secret at every start.
Tests that post to both servers through one helper send one value, so here both are set to TEST_TOKEN. The token
tests (test_*_security.py) still check that a POST without it, or with a wrong one, is refused.
"""
from sewer_app.web import server as _sewer_ui
from water_app.web import server as _water_server

TEST_TOKEN = "test-run-token"
_sewer_ui.TOKEN = _water_server.TOKEN = TEST_TOKEN
AUTH = {"X-App-Token": TEST_TOKEN}
