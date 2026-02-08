import asyncio
import csv
import io
import json
import logging
import re
from datetime import datetime, timezone
from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.dataset.model import (
    Dataset,
    DatasetCreate,
    DatasetItem,
    DatasetItemCreate,
    DatasetItemRead,
    DatasetItemUpdate,
    DatasetRead,
    DatasetReadWithItems,
    DatasetUpdate,
)

router = APIRouter(prefix="/datasets", tags=["Datasets"])


# Dataset CRUD endpoints
@router.post("/", response_model=DatasetRead, status_code=HTTPStatus.CREATED)
async def create_dataset(
    *,
    session: DbSession,
    dataset: DatasetCreate,
    current_user: CurrentActiveUser,
):
    """Create a new empty dataset."""
    db_dataset = Dataset(
        name=dataset.name,
        description=dataset.description,
        user_id=current_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    try:
        session.add(db_dataset)
        await session.commit()
        await session.refresh(db_dataset)
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"A dataset with the name '{dataset.name}' already exists.",
        ) from e

    return DatasetRead(
        id=db_dataset.id,
        name=db_dataset.name,
        description=db_dataset.description,
        dataset_type=db_dataset.dataset_type,
        user_id=db_dataset.user_id,
        created_at=db_dataset.created_at,
        updated_at=db_dataset.updated_at,
        item_count=0,
    )


@router.get("/", response_model=list[DatasetRead], status_code=HTTPStatus.OK)
async def list_datasets(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """List all datasets for the current user."""
    statement = select(Dataset).where(Dataset.user_id == current_user.id).order_by(col(Dataset.created_at).desc())
    result = await session.exec(statement)
    datasets = result.all()

    return [
        DatasetRead(
            id=ds.id,
            name=ds.name,
            description=ds.description,
            dataset_type=ds.dataset_type,
            user_id=ds.user_id,
            created_at=ds.created_at,
            updated_at=ds.updated_at,
            item_count=len(ds.items) if ds.items else 0,
        )
        for ds in datasets
    ]


@router.get("/{dataset_id}", response_model=DatasetReadWithItems, status_code=HTTPStatus.OK)
async def get_dataset(
    *,
    session: DbSession,
    dataset_id: UUID,
    current_user: CurrentActiveUser,
):
    """Get a dataset with all its items."""
    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    result = await session.exec(statement)
    dataset = result.first()

    if not dataset:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")

    # Sort items by order
    sorted_items = sorted(dataset.items, key=lambda x: x.order) if dataset.items else []

    return DatasetReadWithItems(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        dataset_type=dataset.dataset_type,
        user_id=dataset.user_id,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        item_count=len(sorted_items),
        items=[
            DatasetItemRead(
                id=item.id,
                dataset_id=item.dataset_id,
                input=item.input,
                expected_output=item.expected_output,
                order=item.order,
                conversation_id=item.conversation_id,
                created_at=item.created_at,
            )
            for item in sorted_items
        ],
    )


@router.put("/{dataset_id}", response_model=DatasetRead, status_code=HTTPStatus.OK)
async def update_dataset(
    *,
    session: DbSession,
    dataset_id: UUID,
    dataset_update: DatasetUpdate,
    current_user: CurrentActiveUser,
):
    """Update dataset name/description."""
    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    result = await session.exec(statement)
    dataset = result.first()

    if not dataset:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")

    if dataset_update.name is not None:
        dataset.name = dataset_update.name
    if dataset_update.description is not None:
        dataset.description = dataset_update.description

    dataset.updated_at = datetime.now(timezone.utc)

    try:
        session.add(dataset)
        await session.commit()
        await session.refresh(dataset)
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"A dataset with the name '{dataset_update.name}' already exists.",
        ) from e

    return DatasetRead(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        dataset_type=dataset.dataset_type,
        user_id=dataset.user_id,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        item_count=len(dataset.items) if dataset.items else 0,
    )


@router.delete("/{dataset_id}", status_code=HTTPStatus.NO_CONTENT)
async def delete_dataset(
    *,
    session: DbSession,
    dataset_id: UUID,
    current_user: CurrentActiveUser,
) -> None:
    """Delete a dataset and all its items (cascade)."""
    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    result = await session.exec(statement)
    dataset = result.first()

    if not dataset:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")

    await session.delete(dataset)
    await session.commit()


class BulkDeleteRequest(BaseModel):
    dataset_ids: list[UUID]


@router.delete("/", status_code=HTTPStatus.OK)
async def delete_datasets_bulk(
    *,
    session: DbSession,
    request: BulkDeleteRequest,
    current_user: CurrentActiveUser,
) -> dict:
    """Delete multiple datasets."""
    deleted_count = 0
    for dataset_id in request.dataset_ids:
        statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
        result = await session.exec(statement)
        dataset = result.first()
        if dataset:
            await session.delete(dataset)
            deleted_count += 1

    await session.commit()
    return {"deleted": deleted_count}


# Dataset Item CRUD endpoints
@router.post("/{dataset_id}/items", response_model=DatasetItemRead, status_code=HTTPStatus.CREATED)
async def create_dataset_item(
    *,
    session: DbSession,
    dataset_id: UUID,
    item: DatasetItemCreate,
    current_user: CurrentActiveUser,
):
    """Add a single item to a dataset."""
    # Verify dataset exists and belongs to user
    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    result = await session.exec(statement)
    dataset = result.first()

    if not dataset:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")

    # Get the max order for the dataset
    max_order = max((i.order for i in dataset.items), default=-1) if dataset.items else -1

    db_item = DatasetItem(
        dataset_id=dataset_id,
        input=item.input,
        expected_output=item.expected_output,
        order=item.order if item.order > 0 else max_order + 1,
        conversation_id=item.conversation_id,
        created_at=datetime.now(timezone.utc),
    )

    session.add(db_item)

    # Update dataset's updated_at timestamp
    dataset.updated_at = datetime.now(timezone.utc)
    session.add(dataset)

    await session.commit()
    await session.refresh(db_item)

    return DatasetItemRead(
        id=db_item.id,
        dataset_id=db_item.dataset_id,
        input=db_item.input,
        expected_output=db_item.expected_output,
        order=db_item.order,
        conversation_id=db_item.conversation_id,
        created_at=db_item.created_at,
    )


@router.put("/{dataset_id}/items/{item_id}", response_model=DatasetItemRead, status_code=HTTPStatus.OK)
async def update_dataset_item(
    *,
    session: DbSession,
    dataset_id: UUID,
    item_id: UUID,
    item_update: DatasetItemUpdate,
    current_user: CurrentActiveUser,
):
    """Update a dataset item."""
    # Verify dataset exists and belongs to user
    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    result = await session.exec(statement)
    dataset = result.first()

    if not dataset:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")

    # Find the item
    item_statement = select(DatasetItem).where(DatasetItem.id == item_id, DatasetItem.dataset_id == dataset_id)
    item_result = await session.exec(item_statement)
    db_item = item_result.first()

    if not db_item:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset item not found")

    if item_update.input is not None:
        db_item.input = item_update.input
    if item_update.expected_output is not None:
        db_item.expected_output = item_update.expected_output
    if item_update.order is not None:
        db_item.order = item_update.order

    session.add(db_item)

    # Update dataset's updated_at timestamp
    dataset.updated_at = datetime.now(timezone.utc)
    session.add(dataset)

    await session.commit()
    await session.refresh(db_item)

    return DatasetItemRead(
        id=db_item.id,
        dataset_id=db_item.dataset_id,
        input=db_item.input,
        expected_output=db_item.expected_output,
        order=db_item.order,
        conversation_id=db_item.conversation_id,
        created_at=db_item.created_at,
    )


@router.delete("/{dataset_id}/items/{item_id}", status_code=HTTPStatus.NO_CONTENT)
async def delete_dataset_item(
    *,
    session: DbSession,
    dataset_id: UUID,
    item_id: UUID,
    current_user: CurrentActiveUser,
) -> None:
    """Delete a dataset item."""
    # Verify dataset exists and belongs to user
    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    result = await session.exec(statement)
    dataset = result.first()

    if not dataset:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")

    # Find the item
    item_statement = select(DatasetItem).where(DatasetItem.id == item_id, DatasetItem.dataset_id == dataset_id)
    item_result = await session.exec(item_statement)
    db_item = item_result.first()

    if not db_item:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset item not found")

    await session.delete(db_item)

    # Update dataset's updated_at timestamp
    dataset.updated_at = datetime.now(timezone.utc)
    session.add(dataset)

    await session.commit()


# CSV Import/Export endpoints
class CsvImportMapping(BaseModel):
    input_column: str
    expected_output_column: str


@router.post("/{dataset_id}/import/csv", response_model=dict, status_code=HTTPStatus.OK)
async def import_csv(
    *,
    session: DbSession,
    dataset_id: UUID,
    file: UploadFile,
    current_user: CurrentActiveUser,
    input_column: str = "input",
    expected_output_column: str = "expected_output",
):
    """Import items from a CSV file."""
    # Verify dataset exists and belongs to user
    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    result = await session.exec(statement)
    dataset = result.first()

    if not dataset:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")

    # Read CSV file
    content = await file.read()
    try:
        decoded_content = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            decoded_content = content.decode("latin-1")
        except UnicodeDecodeError as e:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Unable to decode CSV file") from e

    # Parse CSV
    reader = csv.DictReader(io.StringIO(decoded_content))

    # Validate columns exist
    fieldnames = reader.fieldnames or []
    if input_column not in fieldnames:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Column '{input_column}' not found in CSV. Available columns: {', '.join(fieldnames)}",
        )
    if expected_output_column not in fieldnames:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Column '{expected_output_column}' not found in CSV. Available columns: {', '.join(fieldnames)}",
        )

    # Auto-detect multi-turn dataset
    has_conversation_id = "conversation_id" in fieldnames
    if has_conversation_id:
        dataset.dataset_type = "multi_turn"

    # Get current max order
    max_order = max((i.order for i in dataset.items), default=-1) if dataset.items else -1

    # Import rows
    imported_count = 0
    for row in reader:
        input_value = row.get(input_column, "")
        expected_output_value = row.get(expected_output_column, "")

        if input_value or expected_output_value:  # Skip completely empty rows
            max_order += 1
            db_item = DatasetItem(
                dataset_id=dataset_id,
                input=input_value,
                expected_output=expected_output_value,
                order=max_order,
                conversation_id=row.get("conversation_id") if has_conversation_id else None,
                created_at=datetime.now(timezone.utc),
            )
            session.add(db_item)
            imported_count += 1

    # Update dataset's updated_at timestamp
    dataset.updated_at = datetime.now(timezone.utc)
    session.add(dataset)

    await session.commit()

    return {"imported": imported_count}


@router.get("/{dataset_id}/export/csv", status_code=HTTPStatus.OK)
async def export_csv(
    *,
    session: DbSession,
    dataset_id: UUID,
    current_user: CurrentActiveUser,
):
    """Export dataset items to a CSV file."""
    # Verify dataset exists and belongs to user
    statement = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    result = await session.exec(statement)
    dataset = result.first()

    if not dataset:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")

    # Create CSV content
    output = io.StringIO()
    writer = csv.writer(output)

    is_multi_turn = dataset.dataset_type == "multi_turn"
    if is_multi_turn:
        writer.writerow(["conversation_id", "input", "expected_output"])
    else:
        writer.writerow(["input", "expected_output"])

    # Sort items by order
    sorted_items = sorted(dataset.items, key=lambda x: x.order) if dataset.items else []

    for item in sorted_items:
        if is_multi_turn:
            writer.writerow([item.conversation_id or "", item.input, item.expected_output])
        else:
            writer.writerow([item.input, item.expected_output])

    output.seek(0)

    # Create filename
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in dataset.name)
    filename = f"{safe_name}_export.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{dataset_id}/columns", response_model=list[str], status_code=HTTPStatus.OK)
async def get_csv_columns(
    *,
    file: UploadFile,
):
    """Get column names from a CSV file (for column mapping UI)."""
    content = await file.read()
    try:
        decoded_content = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            decoded_content = content.decode("latin-1")
        except UnicodeDecodeError as e:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Unable to decode CSV file") from e

    reader = csv.DictReader(io.StringIO(decoded_content))
    return list(reader.fieldnames or [])


@router.post("/preview-csv", response_model=dict, status_code=HTTPStatus.OK)
async def preview_csv(
    *,
    file: UploadFile,
    current_user: CurrentActiveUser,
):
    """Preview CSV file contents and columns for import mapping."""
    content = await file.read()
    try:
        decoded_content = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            decoded_content = content.decode("latin-1")
        except UnicodeDecodeError as e:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Unable to decode CSV file") from e

    reader = csv.DictReader(io.StringIO(decoded_content))
    columns = list(reader.fieldnames or [])

    # Get first 5 rows for preview
    preview_rows = []
    for i, row in enumerate(reader):
        if i >= 5:
            break
        preview_rows.append(dict(row))

    return {"columns": columns, "preview": preview_rows}


# Dataset Generation with LLM
logger = logging.getLogger(__name__)

# In-memory storage for generation metadata (token usage, status).
# Entries are removed when read via the status endpoint.
_generation_metadata: dict[str, dict] = {}

GENERATE_DATASET_TEMPLATE = """Generate exactly {num_items} input/expected_output pairs for the following topic:

{topic}

Return ONLY a valid JSON array with objects containing "input" and "expected_output" keys.
Example format: [{{"input": "...", "expected_output": "..."}}]"""


class DatasetGenerateRequest(BaseModel):
    name: str
    description: str | None = None
    topic: str
    num_items: int = Field(default=10, ge=1, le=50)
    model: dict


async def generate_dataset_items_background(
    dataset_id: UUID,
    user_id: UUID,
    topic: str,
    num_items: int,
    model_config: dict,
):
    """Background task to generate dataset items using an LLM."""
    from langflow.services.deps import session_scope
    from lfx.base.models.unified_models import get_llm, normalize_model_names_to_dicts

    logger.info(f"Starting background dataset generation: dataset_id={dataset_id}")
    try:
        # Enrich model config
        model_name = model_config.get("name")
        enriched_model = dict(model_config)
        if not enriched_model.get("metadata", {}).get("model_class"):
            enriched_models = normalize_model_names_to_dicts(model_name)
            if enriched_models and enriched_models[0].get("metadata", {}).get("model_class"):
                enriched_model = enriched_models[0]
                if model_config.get("provider"):
                    enriched_model["provider"] = model_config["provider"]
            else:
                logger.error(f"Could not find model class for {model_name}")
                return

        llm = get_llm(
            model=[enriched_model],
            user_id=user_id,
            temperature=0.7,
            stream=False,
        )

        prompt = GENERATE_DATASET_TEMPLATE.format(
            num_items=num_items,
            topic=topic,
        )

        response = await llm.ainvoke(prompt)
        output_text = response.content if hasattr(response, "content") else str(response)

        # Extract token usage from the LLM response
        token_usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            token_usage = dict(response.usage_metadata)
        elif hasattr(response, "response_metadata") and response.response_metadata:
            rm = response.response_metadata
            if "token_usage" in rm:
                token_usage = dict(rm["token_usage"])
            elif "usage" in rm:
                token_usage = dict(rm["usage"])

        # Parse JSON response
        json_match = re.search(r"\[.*\]", output_text, re.DOTALL)
        if not json_match:
            logger.error(f"No JSON array found in LLM response: {output_text[:500]}")
            _generation_metadata[str(dataset_id)] = {
                "status": "failed",
                "error": "No JSON array found in LLM response",
                "token_usage": token_usage,
            }
            return
        items_data = json.loads(json_match.group())
        if not isinstance(items_data, list):
            logger.error("LLM response is not a JSON array")
            _generation_metadata[str(dataset_id)] = {
                "status": "failed",
                "error": "LLM response is not a JSON array",
                "token_usage": token_usage,
            }
            return

        # Insert items into the dataset
        async with session_scope() as session:
            for idx, item in enumerate(items_data):
                input_val = item.get("input", "")
                expected_val = item.get("expected_output", "")
                if input_val or expected_val:
                    db_item = DatasetItem(
                        dataset_id=dataset_id,
                        input=str(input_val),
                        expected_output=str(expected_val),
                        order=idx,
                        created_at=datetime.now(timezone.utc),
                    )
                    session.add(db_item)

            # Update dataset timestamp
            statement = select(Dataset).where(Dataset.id == dataset_id)
            result = await session.exec(statement)
            dataset = result.first()
            if dataset:
                dataset.updated_at = datetime.now(timezone.utc)
                session.add(dataset)

            await session.commit()

        item_count = len([i for i in items_data if i.get("input") or i.get("expected_output")])
        _generation_metadata[str(dataset_id)] = {
            "status": "completed",
            "item_count": item_count,
            "token_usage": token_usage,
        }

        logger.info(
            f"Background dataset generation complete: dataset_id={dataset_id}, "
            f"items={item_count}, tokens={token_usage}"
        )

    except Exception as e:
        logger.exception(f"Error in background dataset generation: {e}")
        _generation_metadata[str(dataset_id)] = {
            "status": "failed",
            "error": str(e),
        }


@router.post("/generate", response_model=DatasetRead, status_code=HTTPStatus.CREATED)
async def generate_dataset(
    *,
    session: DbSession,
    request: DatasetGenerateRequest,
    current_user: CurrentActiveUser,
):
    """Create a dataset and generate items in the background using an LLM."""
    model_config = request.model
    model_name = model_config.get("name")
    if not model_name:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="No model name provided",
        )

    # Create dataset immediately (empty)
    db_dataset = Dataset(
        name=request.name,
        description=request.description,
        user_id=current_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    try:
        session.add(db_dataset)
        await session.commit()
        await session.refresh(db_dataset)
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"A dataset with the name '{request.name}' already exists.",
        ) from e

    # Kick off background task to generate items
    asyncio.create_task(
        generate_dataset_items_background(
            dataset_id=db_dataset.id,
            user_id=current_user.id,
            topic=request.topic,
            num_items=request.num_items,
            model_config=model_config,
        )
    )

    return DatasetRead(
        id=db_dataset.id,
        name=db_dataset.name,
        description=db_dataset.description,
        dataset_type=db_dataset.dataset_type,
        user_id=db_dataset.user_id,
        created_at=db_dataset.created_at,
        updated_at=db_dataset.updated_at,
        item_count=0,
    )


@router.get("/generate-status/{dataset_id}", status_code=HTTPStatus.OK)
async def get_generate_status(
    *,
    dataset_id: UUID,
    current_user: CurrentActiveUser,
    consume: bool = True,
) -> dict:
    """Get the generation status and token usage for a dataset."""
    key = str(dataset_id)
    if consume:
        meta = _generation_metadata.pop(key, None)
    else:
        meta = _generation_metadata.get(key)
    if not meta:
        return {"status": "unknown"}
    return meta


class CreateDatasetFromMessagesRequest(BaseModel):
    name: str
    description: str | None = None
    session_ids: list[str]
    flow_id: UUID


@router.post("/from-messages", response_model=DatasetRead, status_code=HTTPStatus.CREATED)
async def create_dataset_from_messages(
    *,
    session: DbSession,
    request: CreateDatasetFromMessagesRequest,
    current_user: CurrentActiveUser,
):
    """Create a multi-turn dataset from existing chat messages."""
    # Create dataset
    db_dataset = Dataset(
        name=request.name,
        description=request.description,
        dataset_type="multi_turn",
        user_id=current_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    try:
        session.add(db_dataset)
        await session.commit()
        await session.refresh(db_dataset)
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"A dataset with the name '{request.name}' already exists.",
        ) from e

    # For each session_id, fetch messages and pair User→Machine turns
    order = 0
    for conv_idx, sid in enumerate(request.session_ids):
        statement = (
            select(MessageTable)
            .where(
                MessageTable.flow_id == request.flow_id,
                MessageTable.session_id == sid,
            )
            .order_by(MessageTable.timestamp.asc())
        )
        result = await session.exec(statement)
        messages = result.all()

        pending_input = None

        for msg in messages:
            if msg.sender == "User":
                pending_input = msg.text
            elif msg.sender == "Machine" and pending_input is not None:
                db_item = DatasetItem(
                    dataset_id=db_dataset.id,
                    input=pending_input,
                    expected_output=msg.text,
                    conversation_id=sid,
                    order=order,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(db_item)
                order += 1
                pending_input = None

    db_dataset.updated_at = datetime.now(timezone.utc)
    session.add(db_dataset)
    await session.commit()

    return DatasetRead(
        id=db_dataset.id,
        name=db_dataset.name,
        description=db_dataset.description,
        dataset_type=db_dataset.dataset_type,
        user_id=db_dataset.user_id,
        created_at=db_dataset.created_at,
        updated_at=db_dataset.updated_at,
        item_count=order,
    )
