import functools
import http.server
import json
import os
import threading

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

from harness import REF, SESSION, Mock  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def base_url():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def open_app(browser, base_url):
    """open_app(Mock(...)) -> (page, mock, js_errors) with a signed-in fake session."""
    ctxs = []

    def _open(mock=None, wait_ms=3000):
        mock = mock or Mock()
        ctx = browser.new_context(viewport={"width": 1100, "height": 900})
        ctxs.append(ctx)
        ctx.add_init_script(f"localStorage.setItem('sb-{REF}-auth-token', {json.dumps(json.dumps(SESSION))});")
        ctx.route("**/*supabase.co/**", mock.handler)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base_url + "/index.html")
        page.wait_for_function("typeof allRoutes!=='undefined' && allRoutes.length>0", timeout=15000)
        page.wait_for_timeout(wait_ms)
        return page, mock, errors

    yield _open
    for c in ctxs:
        c.close()
