"""lfx-supabase: Supabase bundle.

Distribution unit ``lfx-supabase``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:supabase:<Class>@official``.
"""

from lfx_supabase.components.supabase.supabase import SupabaseVectorStoreComponent

__all__ = [
    "SupabaseVectorStoreComponent",
]
