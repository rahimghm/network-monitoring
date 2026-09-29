import dns.exception
import dns.resolver
import pytest

from app.services import dns_resolver


class FakeResolver:
    def __init__(self, answer=None, error=None):
        self.answer = answer
        self.error = error

    def resolve(self, hostname, record_type):
        assert record_type == "A"
        if self.error:
            raise self.error
        return [self.answer]


@pytest.fixture(autouse=True)
def reset_dns_state(monkeypatch):
    monkeypatch.setattr(dns_resolver, "DNS_ENABLED", True)
    monkeypatch.setattr(dns_resolver, "DNS_SERVER", "192.168.56.20")
    monkeypatch.setattr(dns_resolver, "DNS_PORT", 53)
    monkeypatch.setattr(dns_resolver, "DNS_TIMEOUT", 3.0)
    monkeypatch.setattr(dns_resolver, "DNS_DOMAIN", "lab.example")
    dns_resolver._cache.clear()


def test_resolves_fqdn_with_external_dns(monkeypatch):
    monkeypatch.setattr(
        dns_resolver,
        "_configured_resolver",
        lambda: FakeResolver("10.10.10.1"),
    )

    assert dns_resolver.resolve_hostname("ALGIERS-RTR01.lab.example") == "10.10.10.1"


def test_resolves_short_hostname_using_configured_domain(monkeypatch):
    monkeypatch.setattr(
        dns_resolver,
        "_configured_resolver",
        lambda: FakeResolver("10.10.20.1"),
    )

    assert dns_resolver.resolve_hostname("ORAN-RTR01") == "10.10.20.1"


@pytest.mark.parametrize(
    "error",
    [
        dns.resolver.NXDOMAIN(),
        dns.resolver.NoNameservers(),
        dns.exception.Timeout(),
    ],
)
def test_dns_failures_are_reported_as_resolution_errors(monkeypatch, error):
    monkeypatch.setattr(
        dns_resolver,
        "_configured_resolver",
        lambda: FakeResolver(error=error),
    )

    with pytest.raises(dns_resolver.DNSResolutionError):
        dns_resolver.resolve_hostname("missing.lab.example")


def test_dns_disabled_keeps_ip_only_monitoring_available():
    dns_resolver.DNS_ENABLED = False

    assert dns_resolver.resolve_hostname("10.10.10.1") == "10.10.10.1"
    with pytest.raises(dns_resolver.DNSResolutionError, match="DNS is disabled"):
        dns_resolver.resolve_hostname("ALGIERS-RTR01.lab.example")


def test_invalid_dns_configuration_is_reported():
    dns_resolver.DNS_SERVER = "not-an-ip"

    with pytest.raises(dns_resolver.DNSConfigurationError):
        dns_resolver.resolve_hostname("ALGIERS-RTR01.lab.example")


def test_dns_server_unavailable_does_not_use_cached_value(monkeypatch):
    monkeypatch.setattr(
        dns_resolver,
        "_configured_resolver",
        lambda: FakeResolver(error=dns.exception.Timeout()),
    )

    with pytest.raises(dns_resolver.DNSResolutionError):
        dns_resolver.resolve_hostname("ORAN-RTR01.lab.example")