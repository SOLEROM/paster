"""mainBench embed — the family shell frames this app (solBench plan §7).

Rule 1: always send ``frame-ancestors``; the request's own host is trusted
on any port (the shell builds frame URLs from ``location.hostname``);
``BENCH_SHELL_ORIGINS`` covers only a shell on another machine; never send
``X-Frame-Options``. Reference: solSeed's tests/test_bench_embed.py and
solBench/mainBench/framingLessons.md.
"""
import pytest

from server import create_app

SELF_HOST = "'self' http://localhost:* https://localhost:*"


def directive(csp: str, name: str) -> str:
    return [d.strip() for d in csp.split(";") if d.strip().startswith(name)][0]


def page_csp(paths, origins, host=None):
    app, _ = create_app(paths, use_webterm=False, origins_env=origins)
    app.testing = True
    kwargs = {"headers": {"Host": host}} if host else {}
    resp = app.test_client().get("/", **kwargs)
    return resp.headers["Content-Security-Policy"], resp.headers


def test_no_env_still_sends_the_default_deny_header(paths):
    csp, _ = page_csp(paths, "")
    assert directive(csp, "frame-ancestors") == f"frame-ancestors {SELF_HOST}"


@pytest.mark.parametrize("host,pair", [
    ("zvv:6012", "http://zvv:* https://zvv:*"),
    ("laptop.tail1234.ts.net", "http://laptop.tail1234.ts.net:* https://laptop.tail1234.ts.net:*"),
    ("192.168.1.20:6012", "http://192.168.1.20:* https://192.168.1.20:*"),
    ("[::1]:6012", "http://[::1]:* https://[::1]:*"),
])
def test_the_request_host_is_echoed_on_any_port(paths, host, pair):
    csp, _ = page_csp(paths, "", host=host)
    assert directive(csp, "frame-ancestors") == f"frame-ancestors 'self' {pair}"


def test_a_junk_host_header_is_dropped_not_spliced(paths):
    csp, _ = page_csp(paths, "", host="evil host; script-src *")
    assert directive(csp, "frame-ancestors") == "frame-ancestors 'self'"


def test_env_origins_are_added_and_a_trailing_slash_stripped(paths):
    csp, _ = page_csp(paths, "http://edge:6050/ https://shell.ts.net")
    assert directive(csp, "frame-ancestors") == f"frame-ancestors {SELF_HOST} http://edge:6050 https://shell.ts.net"


@pytest.mark.parametrize("bad", ["edge:6050", "http://edge:6050/path", "javascript:alert(1)", "http://a b"])
def test_a_malformed_origin_refuses_to_start(paths, bad):
    with pytest.raises(ValueError):
        create_app(paths, use_webterm=False, origins_env=bad)


def test_x_frame_options_is_never_sent(paths):
    _, headers = page_csp(paths, "")
    assert "X-Frame-Options" not in headers
    app, _ = create_app(paths, use_webterm=False, origins_env="")
    assert "X-Frame-Options" not in app.test_client().get("/api/health").headers


def test_the_unit_template_quotes_the_origins_line():
    """Unquoted, systemd keeps only the first origin (framingLessons #8)."""
    from conftest import REPO_ROOT
    unit = (REPO_ROOT / "deploy" / "systemd" / "paster.service.template").read_text()
    assert 'Environment="BENCH_SHELL_ORIGINS=__BENCH_SHELL_ORIGINS__"' in unit
