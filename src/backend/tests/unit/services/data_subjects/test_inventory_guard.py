import importlib
import pkgutil

import langflow.services.database.models as models_package
from langflow.services.data_subjects.inventory import TABLE_POLICY
from sqlmodel import SQLModel


def _all_tables() -> set[str]:
    for module in pkgutil.walk_packages(models_package.__path__, models_package.__name__ + "."):
        importlib.import_module(module.name)
    return set(SQLModel.metadata.tables)


def test_should_fail_when_a_table_is_missing_from_the_erase_inventory():
    missing = sorted(_all_tables() - set(TABLE_POLICY))

    assert not missing, (
        f"Tables without a data subject erase policy: {missing}. Add each one to "
        "langflow/services/data_subjects/inventory.py with how an erase reaches a person's rows."
    )


def test_should_not_list_tables_that_no_longer_exist():
    stale = sorted(set(TABLE_POLICY) - _all_tables())

    assert not stale, f"Inventory lists tables that do not exist: {stale}"
