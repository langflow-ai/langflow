"""The ``Component`` base every Scavio component derives from.

It deliberately lives *outside* ``components/scavio``. The bundle loader scans
``extension.json``'s ``bundles[].path`` and registers every ``Component`` subclass it
finds there, so a shared base inside that directory would show up in the palette as a
phantom node. Keeping it one level up gives the components a real base class - which is
also what supplies their output methods - without adding anything to the palette.

This module is also the bundle's single entry point into ``lfx``, and ``Output`` is
re-exported for that reason rather than for convenience. Importing
``lfx.template.field.base`` before ``lfx.custom.custom_component.component`` raises
``ImportError: cannot import name 'Component' from partially initialized module``, so
the component modules import both names from here and never reach into ``lfx``
themselves. That keeps the order below the only one that matters.
"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.template.field.base import Output

from lfx_scavio.components.scavio._base import ScavioAPIMixin

__all__ = ["Output", "ScavioBaseComponent"]


class ScavioBaseComponent(ScavioAPIMixin, Component):
    """Carries the Scavio request plumbing and the ``Table`` / ``Raw JSON`` output methods.

    Subclasses supply ``ENDPOINTS``, ``MANAGED_FIELDS``, ``DEFAULT_ENDPOINT``, their
    ``inputs`` and their ``outputs``; everything else is inherited.
    """
