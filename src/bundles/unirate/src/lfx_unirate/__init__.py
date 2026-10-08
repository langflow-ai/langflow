"""lfx-unirate: UniRate currency-conversion bundle.

This package is the distribution unit ``lfx-unirate``.  At runtime Langflow's
loader discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers ``UniRateConversionComponent`` under the namespaced ID
``ext:unirate:UniRateConversionComponent@official``.

UniRate (https://unirateapi.com) is a currency exchange-rate API; the component
calls its convert endpoint directly with ``httpx`` and needs only a
user-supplied API key, so the bundle carries no vendor SDK dependency.
"""

from lfx_unirate.components.unirate.unirate_conversion import UniRateConversionComponent

__all__ = ["UniRateConversionComponent"]
