import ipaddress
import logging
import threading
import time
from typing import Optional

import dns.exception
import dns.resolver

from ..config import (
    DNS_DOMAIN,
    DNS_ENABLED,
    DNS_PORT,
    DNS_SERVER,
    DNS_TIMEOUT,
    HOSTNAME_CACHE_TTL_SECONDS,
)

logger = logging.getLogger(__name__)


class DNSResolutionError(Exception):
    """A configured DNS lookup could not produce an IPv4 address."""


class DNSConfigurationError(DNSResolutionError):
    """The external DNS settings are incomplete or invalid."""


_cache: dict[str, tuple[str, float]] = {}
_cache_lock = threading.Lock()


def _configured_resolver() -> dns.resolver.Resolver:
    if not DNS_SERVER:
        raise DNSConfigurationError("DNS_SERVER must be set when DNS_ENABLED=true")
    try:
        ipaddress.ip_address(DNS_SERVER)
    except ValueError as error:
        raise DNSConfigurationError(f"Invalid DNS_SERVER: {DNS_SERVER}") from error
    if not 1 <= DNS_PORT <= 65535:
        raise DNSConfigurationError(f"Invalid DNS_PORT: {DNS_PORT}")
    if DNS_TIMEOUT <= 0:
        raise DNSConfigurationError(f"Invalid DNS_TIMEOUT: {DNS_TIMEOUT}")

    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = [DNS_SERVER]
    resolver.port = DNS_PORT
    resolver.timeout = DNS_TIMEOUT
    resolver.lifetime = DNS_TIMEOUT
    return resolver


def _qualified_hostname(hostname: str) -> str:
    value = hostname.strip().rstrip(".")
    if not value:
        raise DNSResolutionError("Hostname cannot be empty")
    if "." not in value and DNS_DOMAIN:
        return f"{value}.{DNS_DOMAIN}"
    return value


def resolve_hostname(hostname: str) -> str:
    """Resolve an IPv4 address or hostname using the configured external DNS."""
    value = hostname.strip()
    try:
        address = ipaddress.ip_address(value)
        if address.version != 4:
            raise DNSResolutionError(f"Only IPv4 addresses are supported: '{value}'")
        return str(address)
    except ValueError:
        pass

    if not DNS_ENABLED:
        raise DNSResolutionError(
            f"DNS is disabled; '{value}' must be an IPv4 address"
        )

    qualified = _qualified_hostname(value)
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(qualified.lower())
        if cached and now - cached[1] < HOSTNAME_CACHE_TTL_SECONDS:
            logger.debug("Using cached DNS resolution: %s -> %s", qualified, cached[0])
            return cached[0]

    logger.info("Resolving %s using DNS server %s:%s", qualified, DNS_SERVER, DNS_PORT)
    try:
        answers = _configured_resolver().resolve(qualified, "A")
        address = next(
            str(answer) for answer in answers
            if ipaddress.ip_address(str(answer)).version == 4
        )
    except (dns.exception.DNSException, StopIteration, ValueError) as error:
        logger.warning("DNS resolution failed for %s: %s", qualified, error)
        raise DNSResolutionError(
            f"DNS resolution failed for '{qualified}': {error}"
        ) from error

    with _cache_lock:
        _cache[qualified.lower()] = (address, now)
    logger.info("DNS resolution successful: %s -> %s", qualified, address)
    return address