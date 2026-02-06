# Feature 4: Datasets Feature (Full Stack)

## Summary

Full-stack Datasets feature allowing users to create, manage, and organize input/expected-output pairs for flow evaluation. Includes:

- **Backend**: FastAPI CRUD endpoints for datasets and dataset items, CSV import/export, bulk delete, and column preview
- **Database**: SQLModel models for `Dataset` and `DatasetItem` with Alembic migration
- **Frontend**: React Query hooks for all CRUD operations, datasets list page with AG Grid table, dataset detail page with inline editing, CSV import modal with column mapping and preview, and create dataset modal
- **Navigation**: Datasets page accessible from the main sidebar under Assets

## Dependencies

- Alembic migration `a1b2c3d4e5f6` depends on revision `23c16fac4a0d` (existing migration)
- Evaluations feature (Feature 5) depends on this feature for the `Dataset` model and API
- User model is modified to add the `datasets` relationship (shared with Feature 5 which adds `evaluations`)

## File Diffs

### Backend

#### `src/backend/base/langflow/api/v1/datasets.py` (new)

```diff
diff --git a/src/backend/base/langflow/api/v1/datasets.py b/src/backend/base/langflow/api/v1/datasets.py
new file mode 100644
index 0000000000..b98c25e4e6
--- /dev/null
+++ b/src/backend/base/langflow/api/v1/datasets.py
@@ -0,0 +1,522 @@
+import csv
+import io
+from datetime import datetime, timezone
+from http import HTTPStatus
+from uuid import UUID
+
+from fastapi import APIRouter, HTTPException, UploadFile
+from fastapi.responses import StreamingResponse
+from pydantic import BaseModel
+from sqlalchemy.exc import IntegrityError
+from sqlmodel import col, select
+
+from langflow.api.utils import CurrentActiveUser, DbSession
+from langflow.services.database.models.dataset.model import (
+    Dataset,
+    DatasetCreate,
+    DatasetItem,
+    DatasetItemCreate,
+    DatasetItemRead,
+    DatasetItemUpdate,
+    DatasetRead,
+    DatasetReadWithItems,
+    DatasetUpdate,
+)
+
+router = APIRouter(prefix="/datasets", tags=["Datasets"])
+
+
+# Dataset CRUD endpoints
+@router.post("/", response_model=DatasetRead, status_code=HTTPStatus.CREATED)
+async def create_dataset(
+    *,
+    session: DbSession,
+    dataset: DatasetCreate,
+    current_user: CurrentActiveUser,
+):
+    """Create a new empty dataset."""
+    db_dataset = Dataset(
+        name=dataset.name,
+        description=dataset.description,
+        user_id=current_user.id,
+        created_at=datetime.now(timezone.utc),
+        updated_at=datetime.now(timezone.utc),
+    )
+
+    try:
+        session.add(db_dataset)
+        await session.commit()
+        await session.refresh(db_dataset)
+    except IntegrityError as e:
+        await session.rollback()
+        raise HTTPException(
+            status_code=HTTPStatus.BAD_REQUEST,
+            detail=f"A dataset with the name '{dataset.name}' already exists.",
+        ) from e
+
+    return DatasetRead(
+        id=db_dataset.id,
+        name=db_dataset.name,
+        description=db_dataset.description,
+        user_id=db_dataset.user_id,
+        created_at=db_dataset.created_at,
+        updated_at=db_dataset.updated_at,
+        item_count=0,
+    )
+
+
+@router.get("/", response_model=list[DatasetRead], status_code=HTTPStatus.OK)
+async def list_datasets(
+    *,
+    session: DbSession,
+    current_user: CurrentActiveUser,
+):
+    """List all datasets for the current user."""
+    statement = select(Dataset).where(Dataset.user_id == current_user.id).order_by(col(Dataset.created_at).desc())
+    result = await session.exec(statement)
+    datasets = result.all()
+
+    return [
+        DatasetRead(
+            id=ds.id,
+            name=ds.name,
+            description=ds.description,
+            user_id=ds.user_id,
+            created_at=ds.created_at,
+            updated_at=ds.updated_at,
+            item_count=len(ds.items) if ds.items else 0,
+        )
+        for ds in datasets
+    ]
+
+
+@router.get("/{dataset_id}", response_model=DatasetReadWithItems, status_code=HTTPStatus.OK)
+async def get_dataset(
+    *,
+    session: DbSession,
+    dataset_id: UUID,
+    current_user: CurrentActiveUser,
+):
+    """Get a dataset with all its items."""
+    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
+    result = await session.exec(statement)
+    dataset = result.first()
+
+    if not dataset:
+        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")
+
+    # Sort items by order
+    sorted_items = sorted(dataset.items, key=lambda x: x.order) if dataset.items else []
+
+    return DatasetReadWithItems(
+        id=dataset.id,
+        name=dataset.name,
+        description=dataset.description,
+        user_id=dataset.user_id,
+        created_at=dataset.created_at,
+        updated_at=dataset.updated_at,
+        item_count=len(sorted_items),
+        items=[
+            DatasetItemRead(
+                id=item.id,
+                dataset_id=item.dataset_id,
+                input=item.input,
+                expected_output=item.expected_output,
+                order=item.order,
+                created_at=item.created_at,
+            )
+            for item in sorted_items
+        ],
+    )
+
+
+@router.put("/{dataset_id}", response_model=DatasetRead, status_code=HTTPStatus.OK)
+async def update_dataset(
+    *,
+    session: DbSession,
+    dataset_id: UUID,
+    dataset_update: DatasetUpdate,
+    current_user: CurrentActiveUser,
+):
+    """Update dataset name/description."""
+    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
+    result = await session.exec(statement)
+    dataset = result.first()
+
+    if not dataset:
+        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")
+
+    if dataset_update.name is not None:
+        dataset.name = dataset_update.name
+    if dataset_update.description is not None:
+        dataset.description = dataset_update.description
+
+    dataset.updated_at = datetime.now(timezone.utc)
+
+    try:
+        session.add(dataset)
+        await session.commit()
+        await session.refresh(dataset)
+    except IntegrityError as e:
+        await session.rollback()
+        raise HTTPException(
+            status_code=HTTPStatus.BAD_REQUEST,
+            detail=f"A dataset with the name '{dataset_update.name}' already exists.",
+        ) from e
+
+    return DatasetRead(
+        id=dataset.id,
+        name=dataset.name,
+        description=dataset.description,
+        user_id=dataset.user_id,
+        created_at=dataset.created_at,
+        updated_at=dataset.updated_at,
+        item_count=len(dataset.items) if dataset.items else 0,
+    )
+
+
+@router.delete("/{dataset_id}", status_code=HTTPStatus.NO_CONTENT)
+async def delete_dataset(
+    *,
+    session: DbSession,
+    dataset_id: UUID,
+    current_user: CurrentActiveUser,
+) -> None:
+    """Delete a dataset and all its items (cascade)."""
+    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
+    result = await session.exec(statement)
+    dataset = result.first()
+
+    if not dataset:
+        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")
+
+    await session.delete(dataset)
+    await session.commit()
+
+
+class BulkDeleteRequest(BaseModel):
+    dataset_ids: list[UUID]
+
+
+@router.delete("/", status_code=HTTPStatus.OK)
+async def delete_datasets_bulk(
+    *,
+    session: DbSession,
+    request: BulkDeleteRequest,
+    current_user: CurrentActiveUser,
+) -> dict:
+    """Delete multiple datasets."""
+    deleted_count = 0
+    for dataset_id in request.dataset_ids:
+        statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
+        result = await session.exec(statement)
+        dataset = result.first()
+        if dataset:
+            await session.delete(dataset)
+            deleted_count += 1
+
+    await session.commit()
+    return {"deleted": deleted_count}
+
+
+# Dataset Item CRUD endpoints
+@router.post("/{dataset_id}/items", response_model=DatasetItemRead, status_code=HTTPStatus.CREATED)
+async def create_dataset_item(
+    *,
+    session: DbSession,
+    dataset_id: UUID,
+    item: DatasetItemCreate,
+    current_user: CurrentActiveUser,
+):
+    """Add a single item to a dataset."""
+    # Verify dataset exists and belongs to user
+    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
+    result = await session.exec(statement)
+    dataset = result.first()
+
+    if not dataset:
+        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")
+
+    # Get the max order for the dataset
+    max_order = max((i.order for i in dataset.items), default=-1) if dataset.items else -1
+
+    db_item = DatasetItem(
+        dataset_id=dataset_id,
+        input=item.input,
+        expected_output=item.expected_output,
+        order=item.order if item.order > 0 else max_order + 1,
+        created_at=datetime.now(timezone.utc),
+    )
+
+    session.add(db_item)
+
+    # Update dataset's updated_at timestamp
+    dataset.updated_at = datetime.now(timezone.utc)
+    session.add(dataset)
+
+    await session.commit()
+    await session.refresh(db_item)
+
+    return DatasetItemRead(
+        id=db_item.id,
+        dataset_id=db_item.dataset_id,
+        input=db_item.input,
+        expected_output=db_item.expected_output,
+        order=db_item.order,
+        created_at=db_item.created_at,
+    )
+
+
+@router.put("/{dataset_id}/items/{item_id}", response_model=DatasetItemRead, status_code=HTTPStatus.OK)
+async def update_dataset_item(
+    *,
+    session: DbSession,
+    dataset_id: UUID,
+    item_id: UUID,
+    item_update: DatasetItemUpdate,
+    current_user: CurrentActiveUser,
+):
+    """Update a dataset item."""
+    # Verify dataset exists and belongs to user
+    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
+    result = await session.exec(statement)
+    dataset = result.first()
+
+    if not dataset:
+        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")
+
+    # Find the item
+    item_statement = select(DatasetItem).where(DatasetItem.id == item_id, DatasetItem.dataset_id == dataset_id)
+    item_result = await session.exec(item_statement)
+    db_item = item_result.first()
+
+    if not db_item:
+        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset item not found")
+
+    if item_update.input is not None:
+        db_item.input = item_update.input
+    if item_update.expected_output is not None:
+        db_item.expected_output = item_update.expected_output
+    if item_update.order is not None:
+        db_item.order = item_update.order
+
+    session.add(db_item)
+
+    # Update dataset's updated_at timestamp
+    dataset.updated_at = datetime.now(timezone.utc)
+    session.add(dataset)
+
+    await session.commit()
+    await session.refresh(db_item)
+
+    return DatasetItemRead(
+        id=db_item.id,
+        dataset_id=db_item.dataset_id,
+        input=db_item.input,
+        expected_output=db_item.expected_output,
+        order=db_item.order,
+        created_at=db_item.created_at,
+    )
+
+
+@router.delete("/{dataset_id}/items/{item_id}", status_code=HTTPStatus.NO_CONTENT)
+async def delete_dataset_item(
+    *,
+    session: DbSession,
+    dataset_id: UUID,
+    item_id: UUID,
+    current_user: CurrentActiveUser,
+) -> None:
+    """Delete a dataset item."""
+    # Verify dataset exists and belongs to user
+    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
+    result = await session.exec(statement)
+    dataset = result.first()
+
+    if not dataset:
+        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")
+
+    # Find the item
+    item_statement = select(DatasetItem).where(DatasetItem.id == item_id, DatasetItem.dataset_id == dataset_id)
+    item_result = await session.exec(item_statement)
+    db_item = item_result.first()
+
+    if not db_item:
+        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset item not found")
+
+    await session.delete(db_item)
+
+    # Update dataset's updated_at timestamp
+    dataset.updated_at = datetime.now(timezone.utc)
+    session.add(dataset)
+
+    await session.commit()
+
+
+# CSV Import/Export endpoints
+class CsvImportMapping(BaseModel):
+    input_column: str
+    expected_output_column: str
+
+
+@router.post("/{dataset_id}/import/csv", response_model=dict, status_code=HTTPStatus.OK)
+async def import_csv(
+    *,
+    session: DbSession,
+    dataset_id: UUID,
+    file: UploadFile,
+    current_user: CurrentActiveUser,
+    input_column: str = "input",
+    expected_output_column: str = "expected_output",
+):
+    """Import items from a CSV file."""
+    # Verify dataset exists and belongs to user
+    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
+    result = await session.exec(statement)
+    dataset = result.first()
+
+    if not dataset:
+        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")
+
+    # Read CSV file
+    content = await file.read()
+    try:
+        decoded_content = content.decode("utf-8")
+    except UnicodeDecodeError:
+        try:
+            decoded_content = content.decode("latin-1")
+        except UnicodeDecodeError as e:
+            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Unable to decode CSV file") from e
+
+    # Parse CSV
+    reader = csv.DictReader(io.StringIO(decoded_content))
+
+    # Validate columns exist
+    fieldnames = reader.fieldnames or []
+    if input_column not in fieldnames:
+        raise HTTPException(
+            status_code=HTTPStatus.BAD_REQUEST,
+            detail=f"Column '{input_column}' not found in CSV. Available columns: {', '.join(fieldnames)}",
+        )
+    if expected_output_column not in fieldnames:
+        raise HTTPException(
+            status_code=HTTPStatus.BAD_REQUEST,
+            detail=f"Column '{expected_output_column}' not found in CSV. Available columns: {', '.join(fieldnames)}",
+        )
+
+    # Get current max order
+    max_order = max((i.order for i in dataset.items), default=-1) if dataset.items else -1
+
+    # Import rows
+    imported_count = 0
+    for row in reader:
+        input_value = row.get(input_column, "")
+        expected_output_value = row.get(expected_output_column, "")
+
+        if input_value or expected_output_value:  # Skip completely empty rows
+            max_order += 1
+            db_item = DatasetItem(
+                dataset_id=dataset_id,
+                input=input_value,
+                expected_output=expected_output_value,
+                order=max_order,
+                created_at=datetime.now(timezone.utc),
+            )
+            session.add(db_item)
+            imported_count += 1
+
+    # Update dataset's updated_at timestamp
+    dataset.updated_at = datetime.now(timezone.utc)
+    session.add(dataset)
+
+    await session.commit()
+
+    return {"imported": imported_count}
+
+
+@router.get("/{dataset_id}/export/csv", status_code=HTTPStatus.OK)
+async def export_csv(
+    *,
+    session: DbSession,
+    dataset_id: UUID,
+    current_user: CurrentActiveUser,
+):
+    """Export dataset items to a CSV file."""
+    # Verify dataset exists and belongs to user
+    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
+    result = await session.exec(statement)
+    dataset = result.first()
+
+    if not dataset:
+        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")
+
+    # Create CSV content
+    output = io.StringIO()
+    writer = csv.writer(output)
+    writer.writerow(["input", "expected_output"])
+
+    # Sort items by order
+    sorted_items = sorted(dataset.items, key=lambda x: x.order) if dataset.items else []
+
+    for item in sorted_items:
+        writer.writerow([item.input, item.expected_output])
+
+    output.seek(0)
+
+    # Create filename
+    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in dataset.name)
+    filename = f"{safe_name}_export.csv"
+
+    return StreamingResponse(
+        iter([output.getvalue()]),
+        media_type="text/csv",
+        headers={"Content-Disposition": f"attachment; filename={filename}"},
+    )
+
+
+@router.get("/{dataset_id}/columns", response_model=list[str], status_code=HTTPStatus.OK)
+async def get_csv_columns(
+    *,
+    file: UploadFile,
+):
+    """Get column names from a CSV file (for column mapping UI)."""
+    content = await file.read()
+    try:
+        decoded_content = content.decode("utf-8")
+    except UnicodeDecodeError:
+        try:
+            decoded_content = content.decode("latin-1")
+        except UnicodeDecodeError as e:
+            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Unable to decode CSV file") from e
+
+    reader = csv.DictReader(io.StringIO(decoded_content))
+    return list(reader.fieldnames or [])
+
+
+@router.post("/preview-csv", response_model=dict, status_code=HTTPStatus.OK)
+async def preview_csv(
+    *,
+    file: UploadFile,
+    current_user: CurrentActiveUser,
+):
+    """Preview CSV file contents and columns for import mapping."""
+    content = await file.read()
+    try:
+        decoded_content = content.decode("utf-8")
+    except UnicodeDecodeError:
+        try:
+            decoded_content = content.decode("latin-1")
+        except UnicodeDecodeError as e:
+            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Unable to decode CSV file") from e
+
+    reader = csv.DictReader(io.StringIO(decoded_content))
+    columns = list(reader.fieldnames or [])
+
+    # Get first 5 rows for preview
+    preview_rows = []
+    for i, row in enumerate(reader):
+        if i >= 5:
+            break
+        preview_rows.append(dict(row))
+
+    return {"columns": columns, "preview": preview_rows}
```

#### `src/backend/base/langflow/services/database/models/dataset/__init__.py` (new)

```diff
diff --git a/src/backend/base/langflow/services/database/models/dataset/__init__.py b/src/backend/base/langflow/services/database/models/dataset/__init__.py
new file mode 100644
index 0000000000..315fe92880
--- /dev/null
+++ b/src/backend/base/langflow/services/database/models/dataset/__init__.py
@@ -0,0 +1,23 @@
+from langflow.services.database.models.dataset.model import (
+    Dataset,
+    DatasetCreate,
+    DatasetItem,
+    DatasetItemCreate,
+    DatasetItemRead,
+    DatasetItemUpdate,
+    DatasetRead,
+    DatasetReadWithItems,
+    DatasetUpdate,
+)
+
+__all__ = [
+    "Dataset",
+    "DatasetCreate",
+    "DatasetItem",
+    "DatasetItemCreate",
+    "DatasetItemRead",
+    "DatasetItemUpdate",
+    "DatasetRead",
+    "DatasetReadWithItems",
+    "DatasetUpdate",
+]
```

#### `src/backend/base/langflow/services/database/models/dataset/model.py` (new)

```diff
diff --git a/src/backend/base/langflow/services/database/models/dataset/model.py b/src/backend/base/langflow/services/database/models/dataset/model.py
new file mode 100644
index 0000000000..17cb65a78d
--- /dev/null
+++ b/src/backend/base/langflow/services/database/models/dataset/model.py
@@ -0,0 +1,114 @@
+from datetime import datetime, timezone
+from typing import TYPE_CHECKING
+from uuid import UUID, uuid4
+
+from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, UniqueConstraint, func
+
+if TYPE_CHECKING:
+    from langflow.services.database.models.user.model import User
+
+
+def utc_now():
+    return datetime.now(timezone.utc)
+
+
+# Dataset Models
+class DatasetBase(SQLModel):
+    name: str = Field(description="Name of the dataset", index=True)
+    description: str | None = Field(default=None, description="Description of the dataset")
+
+
+class Dataset(DatasetBase, table=True):  # type: ignore[call-arg]
+    __tablename__ = "dataset"
+    __table_args__ = (UniqueConstraint("user_id", "name", name="unique_dataset_name_per_user"),)
+
+    id: UUID | None = Field(
+        default_factory=uuid4,
+        primary_key=True,
+        description="Unique ID for the dataset",
+    )
+    created_at: datetime | None = Field(
+        default=None,
+        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True),
+        description="Creation time of the dataset",
+    )
+    updated_at: datetime | None = Field(
+        default=None,
+        sa_column=Column(DateTime(timezone=True), nullable=True),
+        description="Last update time of the dataset",
+    )
+    user_id: UUID = Field(description="User ID associated with this dataset", foreign_key="user.id")
+    user: "User" = Relationship(back_populates="datasets")
+    items: list["DatasetItem"] = Relationship(
+        back_populates="dataset",
+        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
+    )
+
+
+class DatasetCreate(DatasetBase):
+    pass
+
+
+class DatasetRead(SQLModel):
+    id: UUID
+    name: str
+    description: str | None = None
+    user_id: UUID
+    created_at: datetime | None = None
+    updated_at: datetime | None = None
+    item_count: int = 0
+
+
+class DatasetReadWithItems(DatasetRead):
+    items: list["DatasetItemRead"] = []
+
+
+class DatasetUpdate(SQLModel):
+    name: str | None = None
+    description: str | None = None
+
+
+# DatasetItem Models
+class DatasetItemBase(SQLModel):
+    input: str = Field(description="Input data as JSON string")
+    expected_output: str = Field(description="Expected output data as JSON string")
+    order: int = Field(default=0, description="Order of the item in the dataset")
+
+
+class DatasetItem(DatasetItemBase, table=True):  # type: ignore[call-arg]
+    __tablename__ = "datasetitem"
+
+    id: UUID | None = Field(
+        default_factory=uuid4,
+        primary_key=True,
+        description="Unique ID for the dataset item",
+    )
+    dataset_id: UUID = Field(
+        description="Dataset ID this item belongs to",
+        foreign_key="dataset.id",
+    )
+    created_at: datetime | None = Field(
+        default=None,
+        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True),
+        description="Creation time of the dataset item",
+    )
+    dataset: Dataset = Relationship(back_populates="items")
+
+
+class DatasetItemCreate(DatasetItemBase):
+    pass
+
+
+class DatasetItemRead(SQLModel):
+    id: UUID
+    dataset_id: UUID
+    input: str
+    expected_output: str
+    order: int
+    created_at: datetime | None = None
+
+
+class DatasetItemUpdate(SQLModel):
+    input: str | None = None
+    expected_output: str | None = None
+    order: int | None = None
```

#### `src/backend/base/langflow/alembic/versions/a1b2c3d4e5f6_create_dataset_tables.py` (new)

```diff
diff --git a/src/backend/base/langflow/alembic/versions/a1b2c3d4e5f6_create_dataset_tables.py b/src/backend/base/langflow/alembic/versions/a1b2c3d4e5f6_create_dataset_tables.py
new file mode 100644
index 0000000000..9e41f7d56a
--- /dev/null
+++ b/src/backend/base/langflow/alembic/versions/a1b2c3d4e5f6_create_dataset_tables.py
@@ -0,0 +1,68 @@
+"""Create dataset tables
+
+Revision ID: a1b2c3d4e5f6
+Revises: 23c16fac4a0d
+Create Date: 2025-02-04 10:00:00.000000
+
+"""
+
+from collections.abc import Sequence
+
+import sqlalchemy as sa
+import sqlmodel
+from alembic import op
+
+from langflow.utils import migration
+
+# revision identifiers, used by Alembic.
+revision: str = "a1b2c3d4e5f6"
+down_revision: str | None = "23c16fac4a0d"
+branch_labels: str | Sequence[str] | None = None
+depends_on: str | Sequence[str] | None = None
+
+
+def upgrade() -> None:
+    conn = op.get_bind()
+
+    # Create dataset table
+    if not migration.table_exists("dataset", conn):
+        op.create_table(
+            "dataset",
+            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
+            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
+            sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
+            sa.Column("user_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
+            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
+            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
+            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
+            sa.PrimaryKeyConstraint("id"),
+            sa.UniqueConstraint("user_id", "name", name="unique_dataset_name_per_user"),
+        )
+        op.create_index(op.f("ix_dataset_name"), "dataset", ["name"], unique=False)
+
+    # Create datasetitem table
+    if not migration.table_exists("datasetitem", conn):
+        op.create_table(
+            "datasetitem",
+            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
+            sa.Column("dataset_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
+            sa.Column("input", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
+            sa.Column("expected_output", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
+            sa.Column("order", sa.Integer(), nullable=False, default=0),
+            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
+            sa.ForeignKeyConstraint(["dataset_id"], ["dataset.id"]),
+            sa.PrimaryKeyConstraint("id"),
+        )
+
+
+def downgrade() -> None:
+    conn = op.get_bind()
+
+    # Drop datasetitem table first (due to FK constraint)
+    if migration.table_exists("datasetitem", conn):
+        op.drop_table("datasetitem")
+
+    # Drop dataset table
+    if migration.table_exists("dataset", conn):
+        op.drop_index(op.f("ix_dataset_name"), table_name="dataset")
+        op.drop_table("dataset")
```

#### `src/backend/base/langflow/services/database/models/user/model.py` (modified -- datasets relationship only)

The full diff of this file includes both `datasets` and `evaluations` relationships. The lines relevant to this feature (datasets) are marked with a comment below.

```diff
diff --git a/src/backend/base/langflow/services/database/models/user/model.py b/src/backend/base/langflow/services/database/models/user/model.py
index e39fe3e68e..21b1262932 100644
--- a/src/backend/base/langflow/services/database/models/user/model.py
+++ b/src/backend/base/langflow/services/database/models/user/model.py
@@ -10,6 +10,8 @@ from langflow.schema.serialize import UUIDstr

 if TYPE_CHECKING:
     from langflow.services.database.models.api_key.model import ApiKey
+    from langflow.services.database.models.dataset.model import Dataset        # <-- DATASETS FEATURE
+    from langflow.services.database.models.evaluation.model import Evaluation  # <-- EVALUATIONS FEATURE (Feature 5)
     from langflow.services.database.models.flow.model import Flow
     from langflow.services.database.models.folder.model import Folder
     from langflow.services.database.models.variable.model import Variable
@@ -46,6 +48,14 @@ class User(SQLModel, table=True):  # type: ignore[call-arg]
         back_populates="user",
         sa_relationship_kwargs={"cascade": "delete"},
     )
+    datasets: list["Dataset"] = Relationship(      # <-- DATASETS FEATURE (this block)
+        back_populates="user",
+        sa_relationship_kwargs={"cascade": "delete"},
+    )
+    evaluations: list["Evaluation"] = Relationship(  # <-- EVALUATIONS FEATURE (Feature 5)
+        back_populates="user",
+        sa_relationship_kwargs={"cascade": "delete"},
+    )
     optins: dict[str, Any] | None = Field(
         sa_column=Column(JSON, default=lambda: UserOptin().model_dump(), nullable=True)
     )
```

### Frontend - API Query Hooks

#### `src/frontend/src/controllers/API/queries/datasets/index.ts` (new)

```diff
diff --git a/src/frontend/src/controllers/API/queries/datasets/index.ts b/src/frontend/src/controllers/API/queries/datasets/index.ts
new file mode 100644
index 0000000000..3e0c2eda15
--- /dev/null
+++ b/src/frontend/src/controllers/API/queries/datasets/index.ts
@@ -0,0 +1,11 @@
+export * from "./use-get-datasets";
+export * from "./use-get-dataset";
+export * from "./use-create-dataset";
+export * from "./use-update-dataset";
+export * from "./use-delete-dataset";
+export * from "./use-delete-datasets";
+export * from "./use-create-dataset-item";
+export * from "./use-update-dataset-item";
+export * from "./use-delete-dataset-item";
+export * from "./use-import-csv";
+export * from "./use-preview-csv";
```

#### `src/frontend/src/controllers/API/queries/datasets/use-create-dataset.ts` (new)

```diff
diff --git a/src/frontend/src/controllers/API/queries/datasets/use-create-dataset.ts b/src/frontend/src/controllers/API/queries/datasets/use-create-dataset.ts
new file mode 100644
index 0000000000..dfee72028b
--- /dev/null
+++ b/src/frontend/src/controllers/API/queries/datasets/use-create-dataset.ts
@@ -0,0 +1,34 @@
+import type { UseMutationResult } from "@tanstack/react-query";
+import type { useMutationFunctionType } from "@/types/api";
+import { api } from "../../api";
+import { getURL } from "../../helpers/constants";
+import { UseRequestProcessor } from "../../services/request-processor";
+import type { DatasetInfo } from "./use-get-datasets";
+
+interface CreateDatasetParams {
+  name: string;
+  description?: string;
+}
+
+export const useCreateDataset: useMutationFunctionType<
+  undefined,
+  CreateDatasetParams
+> = (options?) => {
+  const { mutate, queryClient } = UseRequestProcessor();
+
+  const createDatasetFn = async (
+    params: CreateDatasetParams,
+  ): Promise<DatasetInfo> => {
+    const response = await api.post<DatasetInfo>(`${getURL("DATASETS")}/`, {
+      name: params.name,
+      description: params.description,
+    });
+    queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
+    return response.data;
+  };
+
+  const mutation: UseMutationResult<DatasetInfo, any, CreateDatasetParams> =
+    mutate(["useCreateDataset"], createDatasetFn, options);
+
+  return mutation;
+};
```

#### `src/frontend/src/controllers/API/queries/datasets/use-create-dataset-item.ts` (new)

```diff
diff --git a/src/frontend/src/controllers/API/queries/datasets/use-create-dataset-item.ts b/src/frontend/src/controllers/API/queries/datasets/use-create-dataset-item.ts
new file mode 100644
index 0000000000..33e4e31c29
--- /dev/null
+++ b/src/frontend/src/controllers/API/queries/datasets/use-create-dataset-item.ts
@@ -0,0 +1,46 @@
+import type { UseMutationResult } from "@tanstack/react-query";
+import type { useMutationFunctionType } from "@/types/api";
+import { api } from "../../api";
+import { getURL } from "../../helpers/constants";
+import { UseRequestProcessor } from "../../services/request-processor";
+import type { DatasetItemInfo } from "./use-get-dataset";
+
+interface CreateDatasetItemParams {
+  datasetId: string;
+  input: string;
+  expected_output: string;
+  order?: number;
+}
+
+export const useCreateDatasetItem: useMutationFunctionType<
+  undefined,
+  CreateDatasetItemParams
+> = (options?) => {
+  const { mutate, queryClient } = UseRequestProcessor();
+
+  const createDatasetItemFn = async (
+    params: CreateDatasetItemParams,
+  ): Promise<DatasetItemInfo> => {
+    const response = await api.post<DatasetItemInfo>(
+      `${getURL("DATASETS")}/${params.datasetId}/items`,
+      {
+        input: params.input,
+        expected_output: params.expected_output,
+        order: params.order ?? 0,
+      },
+    );
+    queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
+    queryClient.invalidateQueries({
+      queryKey: ["useGetDataset", params.datasetId],
+    });
+    return response.data;
+  };
+
+  const mutation: UseMutationResult<
+    DatasetItemInfo,
+    any,
+    CreateDatasetItemParams
+  > = mutate(["useCreateDatasetItem"], createDatasetItemFn, options);
+
+  return mutation;
+};
```

#### `src/frontend/src/controllers/API/queries/datasets/use-get-datasets.ts` (new)

```diff
diff --git a/src/frontend/src/controllers/API/queries/datasets/use-get-datasets.ts b/src/frontend/src/controllers/API/queries/datasets/use-get-datasets.ts
new file mode 100644
index 0000000000..5d453d01e9
--- /dev/null
+++ b/src/frontend/src/controllers/API/queries/datasets/use-get-datasets.ts
@@ -0,0 +1,37 @@
+import type { UseQueryResult } from "@tanstack/react-query";
+import type { useQueryFunctionType } from "@/types/api";
+import { api } from "../../api";
+import { getURL } from "../../helpers/constants";
+import { UseRequestProcessor } from "../../services/request-processor";
+
+export interface DatasetInfo {
+  id: string;
+  name: string;
+  description?: string;
+  user_id: string;
+  created_at: string;
+  updated_at: string;
+  item_count: number;
+}
+
+export const useGetDatasets: useQueryFunctionType<undefined, DatasetInfo[]> = (
+  options?,
+) => {
+  const { query } = UseRequestProcessor();
+
+  const getDatasetsFn = async (): Promise<DatasetInfo[]> => {
+    const res = await api.get(`${getURL("DATASETS")}/`);
+    return res.data;
+  };
+
+  const queryResult: UseQueryResult<DatasetInfo[], any> = query(
+    ["useGetDatasets"],
+    getDatasetsFn,
+    {
+      refetchOnWindowFocus: false,
+      ...options,
+    },
+  );
+
+  return queryResult;
+};
```

#### `src/frontend/src/controllers/API/queries/datasets/use-get-dataset.ts` (new)

```diff
diff --git a/src/frontend/src/controllers/API/queries/datasets/use-get-dataset.ts b/src/frontend/src/controllers/API/queries/datasets/use-get-dataset.ts
new file mode 100644
index 0000000000..eb5af62559
--- /dev/null
+++ b/src/frontend/src/controllers/API/queries/datasets/use-get-dataset.ts
@@ -0,0 +1,53 @@
+import type { UseQueryResult } from "@tanstack/react-query";
+import type { useQueryFunctionType } from "@/types/api";
+import { api } from "../../api";
+import { getURL } from "../../helpers/constants";
+import { UseRequestProcessor } from "../../services/request-processor";
+
+export interface DatasetItemInfo {
+  id: string;
+  dataset_id: string;
+  input: string;
+  expected_output: string;
+  order: number;
+  created_at: string;
+}
+
+export interface DatasetWithItems {
+  id: string;
+  name: string;
+  description?: string;
+  user_id: string;
+  created_at: string;
+  updated_at: string;
+  item_count: number;
+  items: DatasetItemInfo[];
+}
+
+interface GetDatasetParams {
+  datasetId: string;
+}
+
+export const useGetDataset: useQueryFunctionType<
+  GetDatasetParams,
+  DatasetWithItems
+> = (params, options?) => {
+  const { query } = UseRequestProcessor();
+
+  const getDatasetFn = async (): Promise<DatasetWithItems> => {
+    const res = await api.get(`${getURL("DATASETS")}/${params.datasetId}`);
+    return res.data;
+  };
+
+  const queryResult: UseQueryResult<DatasetWithItems, any> = query(
+    ["useGetDataset", params.datasetId],
+    getDatasetFn,
+    {
+      refetchOnWindowFocus: false,
+      enabled: !!params.datasetId,
+      ...options,
+    },
+  );
+
+  return queryResult;
+};
```

#### `src/frontend/src/controllers/API/queries/datasets/use-update-dataset.ts` (new)

```diff
diff --git a/src/frontend/src/controllers/API/queries/datasets/use-update-dataset.ts b/src/frontend/src/controllers/API/queries/datasets/use-update-dataset.ts
new file mode 100644
index 0000000000..d6672a8367
--- /dev/null
+++ b/src/frontend/src/controllers/API/queries/datasets/use-update-dataset.ts
@@ -0,0 +1,41 @@
+import type { UseMutationResult } from "@tanstack/react-query";
+import type { useMutationFunctionType } from "@/types/api";
+import { api } from "../../api";
+import { getURL } from "../../helpers/constants";
+import { UseRequestProcessor } from "../../services/request-processor";
+import type { DatasetInfo } from "./use-get-datasets";
+
+interface UpdateDatasetParams {
+  datasetId: string;
+  name?: string;
+  description?: string;
+}
+
+export const useUpdateDataset: useMutationFunctionType<
+  undefined,
+  UpdateDatasetParams
+> = (options?) => {
+  const { mutate, queryClient } = UseRequestProcessor();
+
+  const updateDatasetFn = async (
+    params: UpdateDatasetParams,
+  ): Promise<DatasetInfo> => {
+    const response = await api.put<DatasetInfo>(
+      `${getURL("DATASETS")}/${params.datasetId}`,
+      {
+        name: params.name,
+        description: params.description,
+      },
+    );
+    queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
+    queryClient.invalidateQueries({
+      queryKey: ["useGetDataset", params.datasetId],
+    });
+    return response.data;
+  };
+
+  const mutation: UseMutationResult<DatasetInfo, any, UpdateDatasetParams> =
+    mutate(["useUpdateDataset"], updateDatasetFn, options);
+
+  return mutation;
+};
```

#### `src/frontend/src/controllers/API/queries/datasets/use-update-dataset-item.ts` (new)

```diff
diff --git a/src/frontend/src/controllers/API/queries/datasets/use-update-dataset-item.ts b/src/frontend/src/controllers/API/queries/datasets/use-update-dataset-item.ts
new file mode 100644
index 0000000000..2235f033aa
--- /dev/null
+++ b/src/frontend/src/controllers/API/queries/datasets/use-update-dataset-item.ts
@@ -0,0 +1,47 @@
+import type { UseMutationResult } from "@tanstack/react-query";
+import type { useMutationFunctionType } from "@/types/api";
+import { api } from "../../api";
+import { getURL } from "../../helpers/constants";
+import { UseRequestProcessor } from "../../services/request-processor";
+import type { DatasetItemInfo } from "./use-get-dataset";
+
+interface UpdateDatasetItemParams {
+  datasetId: string;
+  itemId: string;
+  input?: string;
+  expected_output?: string;
+  order?: number;
+}
+
+export const useUpdateDatasetItem: useMutationFunctionType<
+  undefined,
+  UpdateDatasetItemParams
+> = (options?) => {
+  const { mutate, queryClient } = UseRequestProcessor();
+
+  const updateDatasetItemFn = async (
+    params: UpdateDatasetItemParams,
+  ): Promise<DatasetItemInfo> => {
+    const response = await api.put<DatasetItemInfo>(
+      `${getURL("DATASETS")}/${params.datasetId}/items/${params.itemId}`,
+      {
+        input: params.input,
+        expected_output: params.expected_output,
+        order: params.order,
+      },
+    );
+    queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
+    queryClient.invalidateQueries({
+      queryKey: ["useGetDataset", params.datasetId],
+    });
+    return response.data;
+  };
+
+  const mutation: UseMutationResult<
+    DatasetItemInfo,
+    any,
+    UpdateDatasetItemParams
+  > = mutate(["useUpdateDatasetItem"], updateDatasetItemFn, options);
+
+  return mutation;
+};
```

#### `src/frontend/src/controllers/API/queries/datasets/use-delete-dataset.ts` (new)

```diff
diff --git a/src/frontend/src/controllers/API/queries/datasets/use-delete-dataset.ts b/src/frontend/src/controllers/API/queries/datasets/use-delete-dataset.ts
new file mode 100644
index 0000000000..9b39a9d56f
--- /dev/null
+++ b/src/frontend/src/controllers/API/queries/datasets/use-delete-dataset.ts
@@ -0,0 +1,29 @@
+import type { UseMutationResult } from "@tanstack/react-query";
+import type { useMutationFunctionType } from "@/types/api";
+import { api } from "../../api";
+import { getURL } from "../../helpers/constants";
+import { UseRequestProcessor } from "../../services/request-processor";
+
+interface DeleteDatasetParams {
+  datasetId: string;
+}
+
+export const useDeleteDataset: useMutationFunctionType<
+  DeleteDatasetParams,
+  void
+> = (params, options?) => {
+  const { mutate, queryClient } = UseRequestProcessor();
+
+  const deleteDatasetFn = async (): Promise<void> => {
+    await api.delete(`${getURL("DATASETS")}/${params.datasetId}`);
+    queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
+  };
+
+  const mutation: UseMutationResult<void, any, void> = mutate(
+    ["useDeleteDataset"],
+    deleteDatasetFn,
+    options,
+  );
+
+  return mutation;
+};
```

#### `src/frontend/src/controllers/API/queries/datasets/use-delete-datasets.ts` (new)

```diff
diff --git a/src/frontend/src/controllers/API/queries/datasets/use-delete-datasets.ts b/src/frontend/src/controllers/API/queries/datasets/use-delete-datasets.ts
new file mode 100644
index 0000000000..95438c2b08
--- /dev/null
+++ b/src/frontend/src/controllers/API/queries/datasets/use-delete-datasets.ts
@@ -0,0 +1,37 @@
+import type { UseMutationResult } from "@tanstack/react-query";
+import type { useMutationFunctionType } from "@/types/api";
+import { api } from "../../api";
+import { getURL } from "../../helpers/constants";
+import { UseRequestProcessor } from "../../services/request-processor";
+
+interface DeleteDatasetsParams {
+  dataset_ids: string[];
+}
+
+export const useDeleteDatasets: useMutationFunctionType<
+  undefined,
+  DeleteDatasetsParams
+> = (options?) => {
+  const { mutate, queryClient } = UseRequestProcessor();
+
+  const deleteDatasetsFn = async (
+    params: DeleteDatasetsParams,
+  ): Promise<{ deleted: number }> => {
+    const response = await api.delete<{ deleted: number }>(
+      `${getURL("DATASETS")}/`,
+      {
+        data: { dataset_ids: params.dataset_ids },
+      },
+    );
+    queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
+    return response.data;
+  };
+
+  const mutation: UseMutationResult<
+    { deleted: number },
+    any,
+    DeleteDatasetsParams
+  > = mutate(["useDeleteDatasets"], deleteDatasetsFn, options);
+
+  return mutation;
+};
```

#### `src/frontend/src/controllers/API/queries/datasets/use-delete-dataset-item.ts` (new)

```diff
diff --git a/src/frontend/src/controllers/API/queries/datasets/use-delete-dataset-item.ts b/src/frontend/src/controllers/API/queries/datasets/use-delete-dataset-item.ts
new file mode 100644
index 0000000000..c4b229ab8b
--- /dev/null
+++ b/src/frontend/src/controllers/API/queries/datasets/use-delete-dataset-item.ts
@@ -0,0 +1,35 @@
+import type { UseMutationResult } from "@tanstack/react-query";
+import type { useMutationFunctionType } from "@/types/api";
+import { api } from "../../api";
+import { getURL } from "../../helpers/constants";
+import { UseRequestProcessor } from "../../services/request-processor";
+
+interface DeleteDatasetItemParams {
+  datasetId: string;
+  itemId: string;
+}
+
+export const useDeleteDatasetItem: useMutationFunctionType<
+  DeleteDatasetItemParams,
+  void
+> = (params, options?) => {
+  const { mutate, queryClient } = UseRequestProcessor();
+
+  const deleteDatasetItemFn = async (): Promise<void> => {
+    await api.delete(
+      `${getURL("DATASETS")}/${params.datasetId}/items/${params.itemId}`,
+    );
+    queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
+    queryClient.invalidateQueries({
+      queryKey: ["useGetDataset", params.datasetId],
+    });
+  };
+
+  const mutation: UseMutationResult<void, any, void> = mutate(
+    ["useDeleteDatasetItem"],
+    deleteDatasetItemFn,
+    options,
+  );
+
+  return mutation;
+};
```

#### `src/frontend/src/controllers/API/queries/datasets/use-import-csv.ts` (new)

```diff
diff --git a/src/frontend/src/controllers/API/queries/datasets/use-import-csv.ts b/src/frontend/src/controllers/API/queries/datasets/use-import-csv.ts
new file mode 100644
index 0000000000..c28215aeab
--- /dev/null
+++ b/src/frontend/src/controllers/API/queries/datasets/use-import-csv.ts
@@ -0,0 +1,47 @@
+import type { UseMutationResult } from "@tanstack/react-query";
+import type { useMutationFunctionType } from "@/types/api";
+import { api } from "../../api";
+import { getURL } from "../../helpers/constants";
+import { UseRequestProcessor } from "../../services/request-processor";
+
+interface ImportCsvParams {
+  datasetId: string;
+  file: File;
+  inputColumn: string;
+  expectedOutputColumn: string;
+}
+
+export const useImportCsv: useMutationFunctionType<undefined, ImportCsvParams> =
+  (options?) => {
+    const { mutate, queryClient } = UseRequestProcessor();
+
+    const importCsvFn = async (
+      params: ImportCsvParams,
+    ): Promise<{ imported: number }> => {
+      const formData = new FormData();
+      formData.append("file", params.file);
+
+      const response = await api.post<{ imported: number }>(
+        `${getURL("DATASETS")}/${params.datasetId}/import/csv?input_column=${encodeURIComponent(params.inputColumn)}&expected_output_column=${encodeURIComponent(params.expectedOutputColumn)}`,
+        formData,
+        {
+          headers: {
+            "Content-Type": "multipart/form-data",
+          },
+        },
+      );
+      queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
+      queryClient.invalidateQueries({
+        queryKey: ["useGetDataset", params.datasetId],
+      });
+      return response.data;
+    };
+
+    const mutation: UseMutationResult<
+      { imported: number },
+      any,
+      ImportCsvParams
+    > = mutate(["useImportCsv"], importCsvFn, options);
+
+    return mutation;
+  };
```

#### `src/frontend/src/controllers/API/queries/datasets/use-preview-csv.ts` (new)

```diff
diff --git a/src/frontend/src/controllers/API/queries/datasets/use-preview-csv.ts b/src/frontend/src/controllers/API/queries/datasets/use-preview-csv.ts
new file mode 100644
index 0000000000..3bb7a81682
--- /dev/null
+++ b/src/frontend/src/controllers/API/queries/datasets/use-preview-csv.ts
@@ -0,0 +1,46 @@
+import type { UseMutationResult } from "@tanstack/react-query";
+import type { useMutationFunctionType } from "@/types/api";
+import { api } from "../../api";
+import { getURL } from "../../helpers/constants";
+import { UseRequestProcessor } from "../../services/request-processor";
+
+interface PreviewCsvParams {
+  file: File;
+}
+
+interface CsvPreviewResult {
+  columns: string[];
+  preview: Record<string, string>[];
+}
+
+export const usePreviewCsv: useMutationFunctionType<
+  undefined,
+  PreviewCsvParams
+> = (options?) => {
+  const { mutate } = UseRequestProcessor();
+
+  const previewCsvFn = async (
+    params: PreviewCsvParams,
+  ): Promise<CsvPreviewResult> => {
+    const formData = new FormData();
+    formData.append("file", params.file);
+
+    const response = await api.post<CsvPreviewResult>(
+      `${getURL("DATASETS")}/preview-csv`,
+      formData,
+      {
+        headers: {
+          "Content-Type": "multipart/form-data",
+        },
+      },
+    );
+    return response.data;
+  };
+
+  const mutation: UseMutationResult<CsvPreviewResult, any, PreviewCsvParams> =
+    mutate(["usePreviewCsv"], previewCsvFn, {
+      ...options,
+    });
+
+  return mutation;
+};
```

### Frontend - Modals

#### `src/frontend/src/modals/createDatasetModal/index.tsx` (new)

```diff
diff --git a/src/frontend/src/modals/createDatasetModal/index.tsx b/src/frontend/src/modals/createDatasetModal/index.tsx
new file mode 100644
index 0000000000..7437e1ae88
--- /dev/null
+++ b/src/frontend/src/modals/createDatasetModal/index.tsx
@@ -0,0 +1,115 @@
+import { useState } from "react";
+import { Input } from "@/components/ui/input";
+import { Label } from "@/components/ui/label";
+import { Textarea } from "@/components/ui/textarea";
+import { useCreateDataset } from "@/controllers/API/queries/datasets/use-create-dataset";
+import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
+import useAlertStore from "@/stores/alertStore";
+import BaseModal from "../baseModal";
+
+interface CreateDatasetModalProps {
+  open: boolean;
+  setOpen: (open: boolean) => void;
+}
+
+export default function CreateDatasetModal({
+  open,
+  setOpen,
+}: CreateDatasetModalProps): JSX.Element {
+  const [name, setName] = useState("");
+  const [description, setDescription] = useState("");
+  const navigate = useCustomNavigate();
+
+  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
+    setErrorData: state.setErrorData,
+    setSuccessData: state.setSuccessData,
+  }));
+
+  const createDatasetMutation = useCreateDataset({
+    onSuccess: (data) => {
+      setSuccessData({ title: "Dataset created successfully" });
+      setOpen(false);
+      setName("");
+      setDescription("");
+      navigate(`/assets/datasets/${data.id}`);
+    },
+    onError: (error: any) => {
+      setErrorData({
+        title: "Failed to create dataset",
+        list: [
+          error?.response?.data?.detail ||
+            error?.message ||
+            "An unknown error occurred",
+        ],
+      });
+    },
+  });
+
+  const handleSubmit = () => {
+    if (!name.trim()) {
+      setErrorData({
+        title: "Validation error",
+        list: ["Dataset name is required"],
+      });
+      return;
+    }
+
+    createDatasetMutation.mutate({
+      name: name.trim(),
+      description: description.trim() || undefined,
+    });
+  };
+
+  const handleClose = () => {
+    setOpen(false);
+    setName("");
+    setDescription("");
+  };
+
+  if (!open) return <></>;
+
+  return (
+    <BaseModal
+      open={open}
+      setOpen={handleClose}
+      size="small-update"
+      onSubmit={handleSubmit}
+    >
+      <BaseModal.Header description="Create a new dataset to store input/output pairs for evaluation.">
+        Create Dataset
+      </BaseModal.Header>
+      <BaseModal.Content className="flex flex-col gap-4 p-4">
+        <div className="flex flex-col gap-2">
+          <Label htmlFor="dataset-name">
+            Name <span className="text-destructive">*</span>
+          </Label>
+          <Input
+            id="dataset-name"
+            value={name}
+            onChange={(e) => setName(e.target.value)}
+            placeholder="Enter dataset name"
+            autoFocus
+          />
+        </div>
+        <div className="flex flex-col gap-2">
+          <Label htmlFor="dataset-description">Description</Label>
+          <Textarea
+            id="dataset-description"
+            value={description}
+            onChange={(e) => setDescription(e.target.value)}
+            placeholder="Enter dataset description (optional)"
+            rows={3}
+          />
+        </div>
+      </BaseModal.Content>
+      <BaseModal.Footer
+        submit={{
+          label: "Create Dataset",
+          loading: createDatasetMutation.isPending,
+          disabled: !name.trim() || createDatasetMutation.isPending,
+          dataTestId: "btn-create-dataset",
+        }}
+      />
+    </BaseModal>
+  );
+}
```

#### `src/frontend/src/modals/importCsvModal/index.tsx` (new)

```diff
diff --git a/src/frontend/src/modals/importCsvModal/index.tsx b/src/frontend/src/modals/importCsvModal/index.tsx
new file mode 100644
index 0000000000..0043296c71
--- /dev/null
+++ b/src/frontend/src/modals/importCsvModal/index.tsx
@@ -0,0 +1,247 @@
+import { useState } from "react";
+import ForwardedIconComponent from "@/components/common/genericIconComponent";
+import { Button } from "@/components/ui/button";
+import { Label } from "@/components/ui/label";
+import {
+  Select,
+  SelectContent,
+  SelectItem,
+  SelectTrigger,
+  SelectValue,
+} from "@/components/ui/select";
+import { useImportCsv } from "@/controllers/API/queries/datasets/use-import-csv";
+import { usePreviewCsv } from "@/controllers/API/queries/datasets/use-preview-csv";
+import { createFileUpload } from "@/helpers/create-file-upload";
+import useAlertStore from "@/stores/alertStore";
+import BaseModal from "../baseModal";
+
+interface ImportCsvModalProps {
+  open: boolean;
+  setOpen: (open: boolean) => void;
+  datasetId: string;
+  onSuccess?: () => void;
+}
+
+export default function ImportCsvModal({
+  open,
+  setOpen,
+  datasetId,
+  onSuccess,
+}: ImportCsvModalProps): JSX.Element {
+  const [file, setFile] = useState<File | null>(null);
+  const [columns, setColumns] = useState<string[]>([]);
+  const [preview, setPreview] = useState<Record<string, string>[]>([]);
+  const [inputColumn, setInputColumn] = useState<string>("");
+  const [expectedOutputColumn, setExpectedOutputColumn] = useState<string>("");
+
+  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
+    setErrorData: state.setErrorData,
+    setSuccessData: state.setSuccessData,
+  }));
+
+  const previewCsvMutation = usePreviewCsv({
+    onSuccess: (data) => {
+      setColumns(data.columns);
+      setPreview(data.preview);
+      // Auto-select columns if they match common names
+      if (data.columns.includes("input")) {
+        setInputColumn("input");
+      } else if (data.columns.length > 0) {
+        setInputColumn(data.columns[0]);
+      }
+      if (data.columns.includes("expected_output")) {
+        setExpectedOutputColumn("expected_output");
+      } else if (data.columns.includes("output")) {
+        setExpectedOutputColumn("output");
+      } else if (data.columns.length > 1) {
+        setExpectedOutputColumn(data.columns[1]);
+      }
+    },
+    onError: (error: any) => {
+      setErrorData({
+        title: "Failed to parse CSV file",
+        list: [error?.message || "Unable to read the file"],
+      });
+    },
+  });
+
+  const importCsvMutation = useImportCsv({
+    onSuccess: (data) => {
+      setSuccessData({ title: `Successfully imported ${data.imported} items` });
+      handleClose();
+      onSuccess?.();
+    },
+    onError: (error: any) => {
+      setErrorData({
+        title: "Failed to import CSV",
+        list: [
+          error?.response?.data?.detail ||
+            error?.message ||
+            "An unknown error occurred",
+        ],
+      });
+    },
+  });
+
+  const handleSelectFile = async () => {
+    const files = await createFileUpload({
+      accept: ".csv",
+      multiple: false,
+    });
+
+    if (files.length > 0) {
+      const selectedFile = files[0];
+      setFile(selectedFile);
+      previewCsvMutation.mutate({ file: selectedFile });
+    }
+  };
+
+  const handleSubmit = () => {
+    if (!file || !inputColumn || !expectedOutputColumn) {
+      setErrorData({
+        title: "Validation error",
+        list: ["Please select a file and map both columns"],
+      });
+      return;
+    }
+
+    importCsvMutation.mutate({
+      datasetId,
+      file,
+      inputColumn,
+      expectedOutputColumn,
+    });
+  };
+
+  const handleClose = () => {
+    setOpen(false);
+    setFile(null);
+    setColumns([]);
+    setPreview([]);
+    setInputColumn("");
+    setExpectedOutputColumn("");
+  };
+
+  if (!open) return <></>;
+
+  return (
+    <BaseModal open={open} setOpen={handleClose} size="medium-h-full">
+      <BaseModal.Header description="Upload a CSV file and map columns to input/expected output fields.">
+        Import CSV
+      </BaseModal.Header>
+      <BaseModal.Content className="flex flex-col gap-6 p-4">
+        {/* File Upload */}
+        <div
+          onClick={handleSelectFile}
+          className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/25 p-4 transition-colors hover:border-primary/50"
+        >
+          <ForwardedIconComponent
+            name="Upload"
+            className="mb-2 h-6 w-6 text-muted-foreground"
+          />
+          {file ? (
+            <div className="text-center">
+              <p className="font-medium">{file.name}</p>
+              <p className="text-sm text-muted-foreground">
+                Click to replace
+              </p>
+            </div>
+          ) : (
+            <div className="text-center">
+              <p className="font-medium">Click to select CSV file</p>
+              <p className="text-sm text-muted-foreground">
+                or drag and drop
+              </p>
+            </div>
+          )}
+        </div>
+
+        {/* Column Mapping */}
+        {columns.length > 0 && (
+          <div className="flex flex-col gap-4">
+            <h3 className="font-medium">Column Mapping</h3>
+            <div className="grid grid-cols-2 gap-4">
+              <div className="flex flex-col gap-2">
+                <Label>Input Column</Label>
+                <Select value={inputColumn} onValueChange={setInputColumn}>
+                  <SelectTrigger>
+                    <SelectValue placeholder="Select column" />
+                  </SelectTrigger>
+                  <SelectContent>
+                    {columns.map((col) => (
+                      <SelectItem key={col} value={col}>
+                        {col}
+                      </SelectItem>
+                    ))}
+                  </SelectContent>
+                </Select>
+              </div>
+              <div className="flex flex-col gap-2">
+                <Label>Expected Output Column</Label>
+                <Select
+                  value={expectedOutputColumn}
+                  onValueChange={setExpectedOutputColumn}
+                >
+                  <SelectTrigger>
+                    <SelectValue placeholder="Select column" />
+                  </SelectTrigger>
+                  <SelectContent>
+                    {columns.map((col) => (
+                      <SelectItem key={col} value={col}>
+                        {col}
+                      </SelectItem>
+                    ))}
+                  </SelectContent>
+                </Select>
+              </div>
+            </div>
+          </div>
+        )}
+
+        {/* Preview */}
+        {preview.length > 0 && inputColumn && expectedOutputColumn && (
+          <div className="flex flex-col gap-2">
+            <h3 className="font-medium">Preview (first 5 rows)</h3>
+            <div className="overflow-auto rounded-md border">
+              <table className="w-full text-sm">
+                <thead className="sticky top-0 bg-muted">
+                  <tr>
+                    <th className="p-2 text-left font-medium">Input</th>
+                    <th className="p-2 text-left font-medium">
+                      Expected Output
+                    </th>
+                  </tr>
+                </thead>
+                <tbody>
+                  {preview.map((row, idx) => (
+                    <tr key={idx} className="border-t">
+                      <td className="max-w-xs truncate p-2">
+                        {row[inputColumn]}
+                      </td>
+                      <td className="max-w-xs truncate p-2">
+                        {row[expectedOutputColumn]}
+                      </td>
+                    </tr>
+                  ))}
+                </tbody>
+              </table>
+            </div>
+          </div>
+        )}
+      </BaseModal.Content>
+      <BaseModal.Footer
+        submit={{
+          label: "Import",
+          loading: importCsvMutation.isPending,
+          disabled:
+            !file ||
+            !inputColumn ||
+            !expectedOutputColumn ||
+            importCsvMutation.isPending,
+          dataTestId: "btn-import-csv",
+          onClick: handleSubmit,
+        }}
+      />
+    </BaseModal>
+  );
+}
```

### Frontend - Pages

#### `src/frontend/src/pages/MainPage/pages/datasetsPage/index.tsx` (new)

```diff
diff --git a/src/frontend/src/pages/MainPage/pages/datasetsPage/index.tsx b/src/frontend/src/pages/MainPage/pages/datasetsPage/index.tsx
new file mode 100644
index 0000000000..eff84134f7
--- /dev/null
+++ b/src/frontend/src/pages/MainPage/pages/datasetsPage/index.tsx
@@ -0,0 +1,90 @@
+import { useEffect, useState } from "react";
+import ForwardedIconComponent from "@/components/common/genericIconComponent";
+import { SidebarTrigger } from "@/components/ui/sidebar";
+import type { DatasetInfo } from "@/controllers/API/queries/datasets/use-get-datasets";
+import CreateDatasetModal from "@/modals/createDatasetModal";
+import DatasetsTab from "./components/DatasetsTab";
+
+export const DatasetsPage = () => {
+  const [selectedDatasets, setSelectedDatasets] = useState<DatasetInfo[]>([]);
+  const [selectionCount, setSelectionCount] = useState(0);
+  const [isShiftPressed, setIsShiftPressed] = useState(false);
+  const [searchText, setSearchText] = useState("");
+  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
+
+  useEffect(() => {
+    const handleKeyDown = (e: KeyboardEvent) => {
+      if (e.key === "Shift") {
+        setIsShiftPressed(true);
+      }
+    };
+
+    const handleKeyUp = (e: KeyboardEvent) => {
+      if (e.key === "Shift") {
+        setIsShiftPressed(false);
+      }
+    };
+
+    window.addEventListener("keydown", handleKeyDown);
+    window.addEventListener("keyup", handleKeyUp);
+
+    return () => {
+      window.removeEventListener("keydown", handleKeyDown);
+      window.removeEventListener("keyup", handleKeyUp);
+    };
+  }, []);
+
+  const handleCreateDataset = () => {
+    setIsCreateModalOpen(true);
+  };
+
+  const tabProps = {
+    quickFilterText: searchText,
+    setQuickFilterText: setSearchText,
+    selectedDatasets: selectedDatasets,
+    setSelectedDatasets: setSelectedDatasets,
+    quantitySelected: selectionCount,
+    setQuantitySelected: setSelectionCount,
+    isShiftPressed,
+    onCreateDataset: handleCreateDataset,
+  };
+
+  return (
+    <div className="flex h-full w-full" data-testid="datasets-wrapper">
+      <div className="flex h-full w-full flex-col overflow-y-auto transition-all duration-200">
+        <div className="flex h-full w-full flex-col xl:container">
+          <div className="flex flex-1 flex-col justify-start px-5 pt-10">
+            <div className="flex h-full flex-col justify-start">
+              <div
+                className="flex items-center pb-8 text-xl font-semibold"
+                data-testid="mainpage_title"
+              >
+                <div className="h-7 w-10 transition-all group-data-[open=true]/sidebar-wrapper:md:w-0 lg:hidden">
+                  <div className="relative left-0 opacity-100 transition-all group-data-[open=true]/sidebar-wrapper:md:opacity-0">
+                    <SidebarTrigger>
+                      <ForwardedIconComponent
+                        name="PanelLeftOpen"
+                        aria-hidden="true"
+                      />
+                    </SidebarTrigger>
+                  </div>
+                </div>
+                Datasets
+              </div>
+              <div className="flex h-full flex-col">
+                <DatasetsTab {...tabProps} />
+              </div>
+            </div>
+          </div>
+        </div>
+      </div>
+
+      <CreateDatasetModal
+        open={isCreateModalOpen}
+        setOpen={setIsCreateModalOpen}
+      />
+    </div>
+  );
+};
+
+export default DatasetsPage;
```

#### `src/frontend/src/pages/MainPage/pages/datasetsPage/components/DatasetsTab.tsx` (new)

```diff
diff --git a/src/frontend/src/pages/MainPage/pages/datasetsPage/components/DatasetsTab.tsx b/src/frontend/src/pages/MainPage/pages/datasetsPage/components/DatasetsTab.tsx
new file mode 100644
index 0000000000..c43b221f54
--- /dev/null
+++ b/src/frontend/src/pages/MainPage/pages/datasetsPage/components/DatasetsTab.tsx
@@ -0,0 +1,220 @@
+import type {
+  RowClickedEvent,
+  SelectionChangedEvent,
+} from "ag-grid-community";
+import type { AgGridReact } from "ag-grid-react";
+import { useRef, useState } from "react";
+import ForwardedIconComponent from "@/components/common/genericIconComponent";
+import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
+import { Button } from "@/components/ui/button";
+import { Input } from "@/components/ui/input";
+import Loading from "@/components/ui/loading";
+import {
+  type DatasetInfo,
+  useGetDatasets,
+} from "@/controllers/API/queries/datasets/use-get-datasets";
+import { useDeleteDatasets } from "@/controllers/API/queries/datasets/use-delete-datasets";
+import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
+import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
+import useAlertStore from "@/stores/alertStore";
+import { cn } from "@/utils/utils";
+import DatasetEmptyState from "./DatasetEmptyState";
+import DatasetSelectionOverlay from "./DatasetSelectionOverlay";
+import { createDatasetColumns } from "../config/datasetColumns";
+
+interface DatasetsTabProps {
+  quickFilterText: string;
+  setQuickFilterText: (text: string) => void;
+  selectedDatasets: DatasetInfo[];
+  setSelectedDatasets: (datasets: DatasetInfo[]) => void;
+  quantitySelected: number;
+  setQuantitySelected: (quantity: number) => void;
+  isShiftPressed: boolean;
+  onCreateDataset: () => void;
+}
+
+const DatasetsTab = ({
+  quickFilterText,
+  setQuickFilterText,
+  selectedDatasets,
+  setSelectedDatasets,
+  quantitySelected,
+  setQuantitySelected,
+  isShiftPressed,
+  onCreateDataset,
+}: DatasetsTabProps) => {
+  const tableRef = useRef<AgGridReact<any>>(null);
+  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
+    setErrorData: state.setErrorData,
+    setSuccessData: state.setSuccessData,
+  }));
+
+  const navigate = useCustomNavigate();
+
+  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
+  const [datasetsToDelete, setDatasetsToDelete] = useState<DatasetInfo[]>([]);
+
+  const { data: datasets, isLoading, error } = useGetDatasets();
+
+  const deleteDatasetsMutation = useDeleteDatasets({
+    onSuccess: (data) => {
+      setSuccessData({
+        title: `${data.deleted} dataset(s) deleted successfully!`,
+      });
+      resetDeleteState();
+    },
+    onError: (error: any) => {
+      setErrorData({
+        title: "Failed to delete datasets",
+        list: [
+          error?.response?.data?.detail ||
+            error?.message ||
+            "An unknown error occurred",
+        ],
+      });
+      resetDeleteState();
+    },
+  });
+
+  if (error) {
+    setErrorData({
+      title: "Failed to load datasets",
+      list: [error?.message || "An unknown error occurred"],
+    });
+  }
+
+  const resetDeleteState = () => {
+    setDatasetsToDelete([]);
+    setIsDeleteModalOpen(false);
+    setSelectedDatasets([]);
+    setQuantitySelected(0);
+  };
+
+  const handleDeleteSelected = () => {
+    if (selectedDatasets.length > 0) {
+      setDatasetsToDelete(selectedDatasets);
+      setIsDeleteModalOpen(true);
+    }
+  };
+
+  const confirmDelete = () => {
+    if (datasetsToDelete.length > 0 && !deleteDatasetsMutation.isPending) {
+      deleteDatasetsMutation.mutate({
+        dataset_ids: datasetsToDelete.map((d) => d.id),
+      });
+    }
+  };
+
+  const handleSelectionChange = (event: SelectionChangedEvent) => {
+    const selectedRows = event.api.getSelectedRows();
+    setSelectedDatasets(selectedRows);
+    if (selectedRows.length > 0) {
+      setQuantitySelected(selectedRows.length);
+    } else {
+      setTimeout(() => {
+        setQuantitySelected(0);
+      }, 300);
+    }
+  };
+
+  const clearSelection = () => {
+    setQuantitySelected(0);
+    setSelectedDatasets([]);
+    tableRef.current?.api?.deselectAll();
+  };
+
+  const handleRowClick = (event: RowClickedEvent) => {
+    const clickedElement = event.event?.target as HTMLElement;
+    if (clickedElement && !clickedElement.closest("button")) {
+      navigate(`/assets/datasets/${event.data.id}`);
+    }
+  };
+
+  const columnDefs = createDatasetColumns();
+
+  if (isLoading || !datasets || !Array.isArray(datasets)) {
+    return (
+      <div className="flex h-full w-full items-center justify-center">
+        <Loading />
+      </div>
+    );
+  }
+
+  if (datasets.length === 0) {
+    return <DatasetEmptyState onCreateDataset={onCreateDataset} />;
+  }
+
+  return (
+    <div className="flex h-full flex-col pb-4">
+      <div className="flex justify-between">
+        <div className="flex w-full xl:w-5/12">
+          <Input
+            icon="Search"
+            data-testid="search-dataset-input"
+            type="text"
+            placeholder="Search datasets..."
+            className="mr-2 w-full"
+            value={quickFilterText || ""}
+            onChange={(event) => setQuickFilterText(event.target.value)}
+          />
+        </div>
+        <Button
+          className="flex items-center gap-2 font-semibold"
+          onClick={onCreateDataset}
+        >
+          <ForwardedIconComponent name="Plus" /> New Dataset
+        </Button>
+      </div>
+
+      <div className="flex h-full flex-col pt-4">
+        <div className="relative h-full">
+          <TableComponent
+            rowHeight={45}
+            headerHeight={45}
+            cellSelection={false}
+            tableOptions={{
+              hide_options: true,
+            }}
+            suppressRowClickSelection={!isShiftPressed}
+            rowSelection="multiple"
+            onSelectionChanged={handleSelectionChange}
+            onRowClicked={handleRowClick}
+            columnDefs={columnDefs}
+            rowData={datasets}
+            className={cn(
+              "ag-no-border ag-dataset-table group w-full",
+              isShiftPressed && quantitySelected > 0 && "no-select-cells",
+            )}
+            pagination
+            ref={tableRef}
+            quickFilterText={quickFilterText}
+            gridOptions={{
+              stopEditingWhenCellsLoseFocus: true,
+              ensureDomOrder: true,
+              colResizeDefault: "shift",
+            }}
+          />
+
+          <DatasetSelectionOverlay
+            selectedDatasets={selectedDatasets}
+            quantitySelected={quantitySelected}
+            onClearSelection={clearSelection}
+            onDeleteSelected={handleDeleteSelected}
+          />
+        </div>
+      </div>
+
+      <DeleteConfirmationModal
+        open={isDeleteModalOpen}
+        setOpen={setIsDeleteModalOpen}
+        onConfirm={confirmDelete}
+        description={`${datasetsToDelete.length} dataset(s)`}
+        note="This action cannot be undone. All items in the dataset(s) will also be deleted."
+      >
+        <></>
+      </DeleteConfirmationModal>
+    </div>
+  );
+};
+
+export default DatasetsTab;
```

#### `src/frontend/src/pages/MainPage/pages/datasetsPage/components/DatasetEmptyState.tsx` (new)

```diff
diff --git a/src/frontend/src/pages/MainPage/pages/datasetsPage/components/DatasetEmptyState.tsx b/src/frontend/src/pages/MainPage/pages/datasetsPage/components/DatasetEmptyState.tsx
new file mode 100644
index 0000000000..4c11dd00b1
--- /dev/null
+++ b/src/frontend/src/pages/MainPage/pages/datasetsPage/components/DatasetEmptyState.tsx
@@ -0,0 +1,36 @@
+import ForwardedIconComponent from "@/components/common/genericIconComponent";
+import { Button } from "@/components/ui/button";
+
+interface DatasetEmptyStateProps {
+  onCreateDataset: () => void;
+}
+
+const DatasetEmptyState = ({ onCreateDataset }: DatasetEmptyStateProps) => {
+  return (
+    <div className="flex h-full w-full flex-col items-center justify-center gap-8 pb-8">
+      <div className="flex flex-col items-center gap-2">
+        <h3 className="text-2xl font-semibold">No datasets</h3>
+        <p className="text-lg text-secondary-foreground">
+          Create your first dataset to get started.
+        </p>
+      </div>
+      <div className="flex items-center gap-2">
+        <Button
+          onClick={onCreateDataset}
+          className="!px-3 md:!px-4 md:!pl-3.5"
+        >
+          <ForwardedIconComponent
+            name="Plus"
+            aria-hidden="true"
+            className="h-4 w-4"
+          />
+          <span className="whitespace-nowrap font-semibold">
+            Create Dataset
+          </span>
+        </Button>
+      </div>
+    </div>
+  );
+};
+
+export default DatasetEmptyState;
```

#### `src/frontend/src/pages/MainPage/pages/datasetsPage/components/DatasetSelectionOverlay.tsx` (new)

```diff
diff --git a/src/frontend/src/pages/MainPage/pages/datasetsPage/components/DatasetSelectionOverlay.tsx b/src/frontend/src/pages/MainPage/pages/datasetsPage/components/DatasetSelectionOverlay.tsx
new file mode 100644
index 0000000000..e059ae813b
--- /dev/null
+++ b/src/frontend/src/pages/MainPage/pages/datasetsPage/components/DatasetSelectionOverlay.tsx
@@ -0,0 +1,51 @@
+import ForwardedIconComponent from "@/components/common/genericIconComponent";
+import { Button } from "@/components/ui/button";
+import type { DatasetInfo } from "@/controllers/API/queries/datasets/use-get-datasets";
+
+interface DatasetSelectionOverlayProps {
+  selectedDatasets: DatasetInfo[];
+  quantitySelected: number;
+  onClearSelection: () => void;
+  onDeleteSelected: () => void;
+}
+
+const DatasetSelectionOverlay = ({
+  selectedDatasets,
+  quantitySelected,
+  onClearSelection,
+  onDeleteSelected,
+}: DatasetSelectionOverlayProps) => {
+  if (quantitySelected === 0) return null;
+
+  return (
+    <div
+      className={`absolute bottom-0 left-0 right-0 flex h-14 items-center justify-between gap-6 rounded-md border bg-background px-4 shadow-md transition-all duration-300 ${
+        quantitySelected > 0
+          ? "translate-y-0 opacity-100"
+          : "translate-y-4 opacity-0"
+      }`}
+    >
+      <div className="flex items-center gap-2">
+        <span className="text-sm font-semibold">
+          {quantitySelected} selected
+        </span>
+        <Button variant="ghost" size="icon" onClick={onClearSelection}>
+          <ForwardedIconComponent name="X" className="h-4 w-4" />
+        </Button>
+      </div>
+      <div className="flex items-center gap-2">
+        <Button
+          variant="destructive"
+          size="sm"
+          onClick={onDeleteSelected}
+          className="flex items-center gap-2"
+        >
+          <ForwardedIconComponent name="Trash2" className="h-4 w-4" />
+          Delete
+        </Button>
+      </div>
+    </div>
+  );
+};
+
+export default DatasetSelectionOverlay;
```

#### `src/frontend/src/pages/MainPage/pages/datasetsPage/config/datasetColumns.tsx` (new)

```diff
diff --git a/src/frontend/src/pages/MainPage/pages/datasetsPage/config/datasetColumns.tsx b/src/frontend/src/pages/MainPage/pages/datasetsPage/config/datasetColumns.tsx
new file mode 100644
index 0000000000..327a5fc20d
--- /dev/null
+++ b/src/frontend/src/pages/MainPage/pages/datasetsPage/config/datasetColumns.tsx
@@ -0,0 +1,78 @@
+import type { ColDef } from "ag-grid-community";
+import ForwardedIconComponent from "@/components/common/genericIconComponent";
+
+const formatDate = (dateString: string | null | undefined): string => {
+  if (!dateString) return "-";
+  const date = new Date(dateString);
+  return date.toLocaleDateString("en-US", {
+    month: "short",
+    day: "numeric",
+    year: "numeric",
+  });
+};
+
+export const createDatasetColumns = (): ColDef[] => {
+  const baseCellClass =
+    "text-muted-foreground cursor-pointer select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none";
+
+  return [
+    {
+      headerName: "Name",
+      field: "name",
+      flex: 2,
+      sortable: false,
+      headerCheckboxSelection: true,
+      checkboxSelection: true,
+      editable: false,
+      filter: "agTextColumnFilter",
+      cellClass: baseCellClass,
+      cellRenderer: (params: any) => (
+        <div className="flex items-center gap-3 font-medium">
+          <ForwardedIconComponent
+            name="Database"
+            className="h-4 w-4 text-muted-foreground"
+          />
+          <div className="flex flex-col">
+            <div className="text-sm font-medium">{params.value}</div>
+          </div>
+        </div>
+      ),
+    },
+    {
+      headerName: "Description",
+      field: "description",
+      flex: 2,
+      sortable: false,
+      filter: "agTextColumnFilter",
+      editable: false,
+      cellClass: baseCellClass,
+      valueGetter: (params: any) => params.data.description || "-",
+    },
+    {
+      headerName: "Items",
+      field: "item_count",
+      flex: 1,
+      sortable: false,
+      editable: false,
+      cellClass: baseCellClass,
+    },
+    {
+      headerName: "Created",
+      field: "created_at",
+      flex: 1,
+      sortable: false,
+      editable: false,
+      cellClass: baseCellClass,
+      valueFormatter: (params: any) => formatDate(params.value),
+    },
+    {
+      headerName: "Updated",
+      field: "updated_at",
+      flex: 1,
+      sortable: false,
+      editable: false,
+      cellClass: baseCellClass,
+      valueFormatter: (params: any) => formatDate(params.value),
+    },
+  ];
+};
```

#### `src/frontend/src/pages/MainPage/pages/datasetDetailPage/index.tsx` (new)

```diff
diff --git a/src/frontend/src/pages/MainPage/pages/datasetDetailPage/index.tsx b/src/frontend/src/pages/MainPage/pages/datasetDetailPage/index.tsx
new file mode 100644
index 0000000000..97cb3067f8
--- /dev/null
+++ b/src/frontend/src/pages/MainPage/pages/datasetDetailPage/index.tsx
@@ -0,0 +1,369 @@
+import type { CellEditingStoppedEvent, ColDef } from "ag-grid-community";
+import type { AgGridReact } from "ag-grid-react";
+import { useEffect, useRef, useState } from "react";
+import { useParams } from "react-router-dom";
+import ForwardedIconComponent from "@/components/common/genericIconComponent";
+import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
+import { Button } from "@/components/ui/button";
+import { SidebarTrigger } from "@/components/ui/sidebar";
+import Loading from "@/components/ui/loading";
+import {
+  useGetDataset,
+  type DatasetItemInfo,
+} from "@/controllers/API/queries/datasets/use-get-dataset";
+import { useCreateDatasetItem } from "@/controllers/API/queries/datasets/use-create-dataset-item";
+import { useUpdateDatasetItem } from "@/controllers/API/queries/datasets/use-update-dataset-item";
+import { useDeleteDatasetItem } from "@/controllers/API/queries/datasets/use-delete-dataset-item";
+import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
+import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
+import ImportCsvModal from "@/modals/importCsvModal";
+import useAlertStore from "@/stores/alertStore";
+import { getURL } from "@/controllers/API/helpers/constants";
+
+export const DatasetDetailPage = () => {
+  const { datasetId } = useParams<{ datasetId: string }>();
+  const navigate = useCustomNavigate();
+  const tableRef = useRef<AgGridReact<any>>(null);
+
+  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
+    setErrorData: state.setErrorData,
+    setSuccessData: state.setSuccessData,
+  }));
+
+  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
+  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
+  const [itemToDelete, setItemToDelete] = useState<DatasetItemInfo | null>(
+    null,
+  );
+
+  const {
+    data: dataset,
+    isLoading,
+    error,
+    refetch,
+  } = useGetDataset({ datasetId: datasetId || "" });
+
+  const createItemMutation = useCreateDatasetItem({
+    onSuccess: () => {
+      setSuccessData({ title: "Item added successfully" });
+      refetch();
+    },
+    onError: (error: any) => {
+      setErrorData({
+        title: "Failed to add item",
+        list: [error?.message || "An unknown error occurred"],
+      });
+    },
+  });
+
+  const updateItemMutation = useUpdateDatasetItem({
+    onSuccess: () => {
+      setSuccessData({ title: "Item updated successfully" });
+      refetch();
+    },
+    onError: (error: any) => {
+      setErrorData({
+        title: "Failed to update item",
+        list: [error?.message || "An unknown error occurred"],
+      });
+    },
+  });
+
+  const handleDeleteItem = (item: DatasetItemInfo) => {
+    setItemToDelete(item);
+    setIsDeleteModalOpen(true);
+  };
+
+  const deleteItemMutation = useDeleteDatasetItem(
+    {
+      datasetId: datasetId || "",
+      itemId: itemToDelete?.id || "",
+    },
+    {
+      onSuccess: () => {
+        setSuccessData({ title: "Item deleted successfully" });
+        setItemToDelete(null);
+        setIsDeleteModalOpen(false);
+        refetch();
+      },
+      onError: (error: any) => {
+        setErrorData({
+          title: "Failed to delete item",
+          list: [error?.message || "An unknown error occurred"],
+        });
+        setItemToDelete(null);
+        setIsDeleteModalOpen(false);
+      },
+    },
+  );
+
+  const handleAddItem = () => {
+    if (datasetId) {
+      createItemMutation.mutate({
+        datasetId,
+        input: "",
+        expected_output: "",
+      });
+    }
+  };
+
+  const handleCellEditingStopped = (event: CellEditingStoppedEvent) => {
+    const { data, colDef, newValue, oldValue } = event;
+    if (newValue !== oldValue && colDef.field && datasetId) {
+      updateItemMutation.mutate({
+        datasetId,
+        itemId: data.id,
+        [colDef.field]: newValue,
+      });
+    }
+  };
+
+  const handleExport = () => {
+    if (datasetId) {
+      window.open(`${getURL("DATASETS")}/${datasetId}/export/csv`, "_blank");
+    }
+  };
+
+  const handleBack = () => {
+    navigate("/assets/datasets");
+  };
+
+  const columnDefs: ColDef[] = [
+    {
+      headerName: "#",
+      field: "order",
+      width: 70,
+      sortable: false,
+      editable: false,
+      cellClass: "text-muted-foreground",
+      valueGetter: (params: any) => (params.node?.rowIndex ?? 0) + 1,
+    },
+    {
+      headerName: "Input",
+      field: "input",
+      flex: 2,
+      sortable: false,
+      editable: true,
+      cellClass: "cursor-text",
+      cellEditor: "agLargeTextCellEditor",
+      cellEditorPopup: true,
+      cellEditorParams: {
+        maxLength: 10000,
+        rows: 10,
+        cols: 50,
+      },
+    },
+    {
+      headerName: "Expected Output",
+      field: "expected_output",
+      flex: 2,
+      sortable: false,
+      editable: true,
+      cellClass: "cursor-text",
+      cellEditor: "agLargeTextCellEditor",
+      cellEditorPopup: true,
+      cellEditorParams: {
+        maxLength: 10000,
+        rows: 10,
+        cols: 50,
+      },
+    },
+    {
+      headerName: "",
+      field: "actions",
+      width: 60,
+      sortable: false,
+      editable: false,
+      cellRenderer: (params: any) => (
+        <Button
+          variant="ghost"
+          size="icon"
+          onClick={(e) => {
+            e.stopPropagation();
+            handleDeleteItem(params.data);
+          }}
+          className="h-8 w-8 text-muted-foreground hover:text-destructive"
+        >
+          <ForwardedIconComponent name="Trash2" className="h-4 w-4" />
+        </Button>
+      ),
+    },
+  ];
+
+  if (error) {
+    return (
+      <div className="flex h-full w-full items-center justify-center">
+        <div className="text-center">
+          <p className="text-destructive">Failed to load dataset</p>
+          <Button variant="outline" onClick={handleBack} className="mt-4">
+            Go Back
+          </Button>
+        </div>
+      </div>
+    );
+  }
+
+  if (isLoading || !dataset) {
+    return (
+      <div className="flex h-full w-full items-center justify-center">
+        <Loading />
+      </div>
+    );
+  }
+
+  return (
+    <div className="flex h-full w-full" data-testid="dataset-detail-wrapper">
+      <div className="flex h-full w-full flex-col overflow-y-auto transition-all duration-200">
+        <div className="flex h-full w-full flex-col xl:container">
+          <div className="flex flex-1 flex-col justify-start px-5 pt-10">
+            <div className="flex h-full flex-col justify-start">
+              {/* Header */}
+              <div className="flex items-center justify-between pb-8">
+                <div className="flex items-center gap-4">
+                  <div className="h-7 w-10 transition-all group-data-[open=true]/sidebar-wrapper:md:w-0 lg:hidden">
+                    <div className="relative left-0 opacity-100 transition-all group-data-[open=true]/sidebar-wrapper:md:opacity-0">
+                      <SidebarTrigger>
+                        <ForwardedIconComponent
+                          name="PanelLeftOpen"
+                          aria-hidden="true"
+                        />
+                      </SidebarTrigger>
+                    </div>
+                  </div>
+                  <Button
+                    variant="ghost"
+                    size="icon"
+                    onClick={handleBack}
+                    className="mr-2"
+                  >
+                    <ForwardedIconComponent name="ArrowLeft" className="h-5 w-5" />
+                  </Button>
+                  <div className="flex items-center gap-2">
+                    <ForwardedIconComponent
+                      name="Database"
+                      className="h-5 w-5 text-muted-foreground"
+                    />
+                    <h1 className="text-xl font-semibold">{dataset.name}</h1>
+                    {dataset.description && (
+                      <span className="text-sm text-muted-foreground">
+                        - {dataset.description}
+                      </span>
+                    )}
+                  </div>
+                </div>
+                <div className="flex items-center gap-2">
+                  <Button
+                    variant="outline"
+                    onClick={() => setIsImportModalOpen(true)}
+                    className="flex items-center gap-2"
+                  >
+                    <ForwardedIconComponent name="Upload" className="h-4 w-4" />
+                    Import CSV
+                  </Button>
+                  <Button
+                    variant="outline"
+                    onClick={handleExport}
+                    className="flex items-center gap-2"
+                  >
+                    <ForwardedIconComponent name="Download" className="h-4 w-4" />
+                    Export
+                  </Button>
+                  <Button
+                    onClick={handleAddItem}
+                    className="flex items-center gap-2"
+                    disabled={createItemMutation.isPending}
+                  >
+                    <ForwardedIconComponent name="Plus" className="h-4 w-4" />
+                    Add Item
+                  </Button>
+                </div>
+              </div>
+
+              {/* Table */}
+              <div className="flex h-full flex-col pb-4">
+                <div className="relative h-full">
+                  {dataset.items.length === 0 ? (
+                    <div className="flex h-full flex-col items-center justify-center gap-4 py-20">
+                      <ForwardedIconComponent
+                        name="Database"
+                        className="h-12 w-12 text-muted-foreground"
+                      />
+                      <p className="text-lg text-muted-foreground">
+                        No items in this dataset yet
+                      </p>
+                      <div className="flex gap-2">
+                        <Button
+                          variant="outline"
+                          onClick={() => setIsImportModalOpen(true)}
+                        >
+                          <ForwardedIconComponent
+                            name="Upload"
+                            className="mr-2 h-4 w-4"
+                          />
+                          Import CSV
+                        </Button>
+                        <Button onClick={handleAddItem}>
+                          <ForwardedIconComponent
+                            name="Plus"
+                            className="mr-2 h-4 w-4"
+                          />
+                          Add Item
+                        </Button>
+                      </div>
+                    </div>
+                  ) : (
+                    <TableComponent
+                      rowHeight={60}
+                      headerHeight={45}
+                      cellSelection={false}
+                      tableOptions={{
+                        hide_options: true,
+                      }}
+                      columnDefs={columnDefs}
+                      rowData={dataset.items}
+                      className="ag-no-border ag-dataset-detail-table w-full"
+                      pagination
+                      ref={tableRef}
+                      onCellEditingStopped={handleCellEditingStopped}
+                      gridOptions={{
+                        stopEditingWhenCellsLoseFocus: true,
+                        ensureDomOrder: true,
+                        colResizeDefault: "shift",
+                        singleClickEdit: false,
+                      }}
+                    />
+                  )}
+                </div>
+              </div>
+            </div>
+          </div>
+        </div>
+      </div>
+
+      <ImportCsvModal
+        open={isImportModalOpen}
+        setOpen={setIsImportModalOpen}
+        datasetId={datasetId || ""}
+        onSuccess={() => {
+          refetch();
+        }}
+      />
+
+      <DeleteConfirmationModal
+        open={isDeleteModalOpen}
+        setOpen={setIsDeleteModalOpen}
+        onConfirm={() => {
+          if (!deleteItemMutation.isPending) {
+            deleteItemMutation.mutate();
+          }
+        }}
+        description="this item"
+        note="This action cannot be undone."
+      >
+        <></>
+      </DeleteConfirmationModal>
+    </div>
+  );
+};
+
+export default DatasetDetailPage;
```

## Implementation Notes

1. **Database Schema**: Two tables (`dataset`, `datasetitem`) with a one-to-many relationship. Datasets are scoped per user via a unique constraint on `(user_id, name)`. Items use an `order` field for maintaining sequence.

2. **Cascade Deletes**: Dataset items are automatically deleted when a dataset is deleted (via SQLAlchemy cascade). The User model also cascades dataset deletion when a user is removed.

3. **CSV Import Flow**: The import uses a two-step process: first, the frontend calls `preview-csv` to get column names and sample rows, then the user maps columns and confirms the import. This allows handling of arbitrary CSV schemas.

4. **Inline Editing**: The dataset detail page uses AG Grid's built-in cell editing with `agLargeTextCellEditor` for input/expected_output fields. Edits are saved on cell blur via `onCellEditingStopped`.

5. **Bulk Operations**: The datasets list page supports multi-select (via Shift+Click) and bulk delete, following the same pattern as the existing flows list page.

6. **Shared Files**: This feature also requires changes to shared files (router registration, route definitions, constants, sidebar navigation) which are documented in a separate shared infrastructure feature document.

7. **API URL Constant**: The frontend expects a `DATASETS` key in the URL constants (`getURL("DATASETS")`), which maps to `/api/v1/datasets`.
