"""The terminal answers loopback plus the tailnet, never the LAN by default."""
from modules.webterm_integration import trusted_networks

TAILNET = "100.64.0.0/10"


def test_the_tailnet_is_trusted_by_default(monkeypatch):
    monkeypatch.delenv("PASTER_WEBTERM_TRUSTED_NETS", raising=False)
    assert trusted_networks(TAILNET) == (TAILNET,)


def test_the_env_overrides_the_list(monkeypatch):
    monkeypatch.setenv("PASTER_WEBTERM_TRUSTED_NETS", " 10.1.0.0/16, ,100.64.0.0/10 ")
    assert trusted_networks(TAILNET) == ("10.1.0.0/16", TAILNET)


def test_an_empty_env_means_loopback_only(monkeypatch):
    monkeypatch.setenv("PASTER_WEBTERM_TRUSTED_NETS", "")
    assert trusted_networks(TAILNET) == ()
