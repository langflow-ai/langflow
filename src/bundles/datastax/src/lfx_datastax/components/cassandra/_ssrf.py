"""Validate Cassandra seed and discovered peer destinations before driver connections."""

from cassandra.policies import AddressTranslator
from lfx.utils.ssrf_protection import (
    is_connector_ssrf_validation_enabled,
    is_ssrf_protection_enabled,
    validate_connector_hostname_for_ssrf,
)


class _ValidatingAddressTranslator(AddressTranslator):
    def __init__(self, delegate: AddressTranslator | None) -> None:
        self._delegate = delegate

    def translate(self, addr: str) -> str:
        target = self._delegate.translate(addr) if self._delegate is not None else addr
        validate_connector_hostname_for_ssrf(target)
        return target


def validate_cassandra_connection(contact_points: str | list[str], cluster_kwargs: dict | None) -> dict:
    """Check seed hosts and wrap the driver's public peer address translator hook."""
    if not is_connector_ssrf_validation_enabled() or not is_ssrf_protection_enabled():
        return cluster_kwargs or {}

    for host in contact_points if isinstance(contact_points, list) else [contact_points]:
        validate_connector_hostname_for_ssrf(host.strip())

    options = dict(cluster_kwargs or {})
    options["address_translator"] = _ValidatingAddressTranslator(options.get("address_translator"))
    return options
