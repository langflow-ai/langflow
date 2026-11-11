"""Check the built wheel's real metadata, component loader, and server entry point."""

from __future__ import annotations

import importlib
import importlib.metadata
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

COMPONENT_NAMES = {
    "SalesforceReadRecordComponent",
    "SalesforceCreateRecordComponent",
    "SalesforceUpdateRecordComponent",
    "SalesforceOnRecordTriggerComponent",
}


def require(condition: bool, message: str) -> None:  # noqa: FBT001 - assertion helper
    if not condition:
        raise RuntimeError(message)


def verify(wheel: Path) -> None:
    with TemporaryDirectory(prefix="lfx-salesforce-wheel-") as temporary:
        target = Path(temporary).resolve()
        with ZipFile(wheel) as archive:
            for name in archive.namelist():
                if not (target / name).resolve().is_relative_to(target):
                    msg = "The wheel contains an unsafe member path."
                    raise ValueError(msg)
            archive.extractall(target)
        sys.path.insert(0, str(target))
        importlib.invalidate_caches()
        import lfx_salesforce
        from lfx.extension import load_installed_extensions
        from lfx.extension.bundle_registry import BundleRecord, get_default_registry

        require(
            Path(lfx_salesforce.__file__).is_relative_to(target), "The source package shadowed the installed wheel."
        )
        distribution = importlib.metadata.distribution("lfx-salesforce")
        require(distribution.version == "0.1.0", "The wheel version is incorrect.")
        loaded = load_installed_extensions([distribution])
        require(len(loaded) == 1, "The installed bundle was not discovered.")
        result = loaded[0]
        require(result.ok, "The installed bundle failed validation or component loading.")
        require(
            {component.class_name for component in result.components} == COMPONENT_NAMES,
            "The installed components do not match the supported surface.",
        )
        require(len(result.integrations) == 1, "The capability manifest was not installed.")
        get_default_registry().install_bundle(
            BundleRecord(
                bundle="salesforce",
                extension_id="lfx-salesforce",
                extension_version="0.1.0",
                slot="official",
                components=tuple(result.components),
                integrations=tuple(result.integrations),
                distribution="lfx-salesforce",
                source_path=result.source_path,
            )
        )
        from langflow.services.triggers.providers.registry import get_provider

        provider = get_provider("salesforce")
        require(provider is not None, "The owned server provider entry point was not discovered.")
        require(
            provider.kinds[0].component == "SalesforceOnRecordTriggerComponent", "The trigger identity is incorrect."
        )
        require(provider.oauth is not None and provider.collect is not None, "The provider hooks are unavailable.")
        sys.stdout.write(
            "Installed wheel verified. Four components, one integration, one owned server provider, and OAuth hooks.\n"
        )


if __name__ == "__main__":
    verify(Path(sys.argv[1]).resolve())
