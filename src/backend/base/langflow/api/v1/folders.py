from typing import Annotated

import orjson
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi_pagination import Params
from fastapi_pagination.ext.sqlmodel import paginate
from sqlalchemy import or_, update
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession, cascade_delete_flow, custom_params
from langflow.api.v1.flows import create_flows
from langflow.api.v1.schemas import FlowListCreate, FlowListReadWithFolderName
from langflow.helpers.flow import generate_unique_flow_name
from langflow.helpers.folders import generate_unique_folder_name
from langflow.initial_setup.setup import STARTER_FOLDER_NAME
from langflow.services.database.models.flow.model import Flow, FlowCreate, FlowRead
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import (
    Folder,
    FolderCreate,
    FolderRead,
    FolderReadWithFlows,
    FolderUpdate,
)
from langflow.services.database.models.folder.pagination_model import FolderWithPaginatedFlows

router = APIRouter(prefix="/folders", tags=["Folders"])


@router.post("/", response_model=FolderRead, status_code=201)
async def create_folder(
    *,
    session: DbSession,
    folder: FolderCreate,
    current_user: CurrentActiveUser,
):
    try:
        new_folder = Folder.model_validate(folder, from_attributes=True)
        new_folder.user_id = current_user.id
        # First check if the folder.name is unique
        # there might be flows with name like: "MyFlow", "MyFlow (1)", "MyFlow (2)"
        # so we need to check if the name is unique with `like` operator
        # if we find a flow with the same name, we add a number to the end of the name
        # based on the highest number found
        if session.exec(
            statement=select(Folder).where(Folder.name == new_folder.name).where(Folder.user_id == current_user.id)
        ).first():
            folder_results = session.exec(
                select(Folder).where(
                    Folder.name.like(f"{new_folder.name}%"),  # type: ignore[attr-defined]
                    Folder.user_id == current_user.id,
                )
            )
            if folder_results:
                folder_names = [folder.name for folder in folder_results]
                folder_numbers = [int(name.split("(")[-1].split(")")[0]) for name in folder_names if "(" in name]
                if folder_numbers:
                    new_folder.name = f"{new_folder.name} ({max(folder_numbers) + 1})"
                else:
                    new_folder.name = f"{new_folder.name} (1)"

        session.add(new_folder)
        session.commit()
        session.refresh(new_folder)

        if folder.components_list:
            update_statement_components = (
                update(Flow).where(Flow.id.in_(folder.components_list)).values(folder_id=new_folder.id)  # type: ignore[attr-defined]
            )
            session.exec(update_statement_components)
            session.commit()

        if folder.flows_list:
            update_statement_flows = update(Flow).where(Flow.id.in_(folder.flows_list)).values(folder_id=new_folder.id)  # type: ignore[attr-defined]
            session.exec(update_statement_flows)
            session.commit()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return new_folder


@router.get("/", response_model=list[FolderRead], status_code=200)
async def read_folders(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    try:
        folders = session.exec(
            select(Folder).where(
                or_(Folder.user_id == current_user.id, Folder.user_id == None)  # noqa: E711
            )
        ).all()
        folders = [folder for folder in folders if folder.name != STARTER_FOLDER_NAME]
        return sorted(folders, key=lambda x: x.name != DEFAULT_FOLDER_NAME)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{folder_id}", response_model=FolderWithPaginatedFlows | FolderReadWithFlows, status_code=200)
async def read_folder(
    *,
    session: DbSession,
    folder_id: str,
    current_user: CurrentActiveUser,
    params: Annotated[Params | None, Depends(custom_params)],
    is_component: bool = False,
    is_flow: bool = False,
    search: str = "",
):
    try:
        folder = session.exec(select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id)).first()
    except Exception as e:
        if "No result found" in str(e):
            raise HTTPException(status_code=404, detail="Folder not found") from e
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    try:
        if params and params.page and params.size:
            stmt = select(Flow).where(Flow.folder_id == folder_id)

            if Flow.updated_at is not None:
                stmt = stmt.order_by(Flow.updated_at.desc())  # type: ignore[attr-defined]
            if is_component:
                stmt = stmt.where(Flow.is_component == True)  # noqa: E712
            if is_flow:
                stmt = stmt.where(Flow.is_component == False)  # noqa: E712
            if search:
                stmt = stmt.where(Flow.name.like(f"%{search}%"))  # type: ignore[attr-defined]
            paginated_flows = paginate(session, stmt, params=params)

            return FolderWithPaginatedFlows(folder=FolderRead.model_validate(folder), flows=paginated_flows)

        flows_from_current_user_in_folder = [flow for flow in folder.flows if flow.user_id == current_user.id]
        folder.flows = flows_from_current_user_in_folder
        return folder  # noqa: TRY300

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{folder_id}", response_model=FolderRead, status_code=200)
async def update_folder(
    *,
    session: DbSession,
    folder_id: str,
    folder: FolderUpdate,  # Assuming FolderUpdate is a Pydantic model defining updatable fields
    current_user: CurrentActiveUser,
):
    try:
        existing_folder = session.exec(
            select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id)
        ).first()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not existing_folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    try:
        if folder.name and folder.name != existing_folder.name:
            existing_folder.name = folder.name
            session.add(existing_folder)
            session.commit()
            session.refresh(existing_folder)
            return existing_folder

        folder_data = existing_folder.model_dump(exclude_unset=True)
        for key, value in folder_data.items():
            if key not in {"components", "flows"}:
                setattr(existing_folder, key, value)
        session.add(existing_folder)
        session.commit()
        session.refresh(existing_folder)

        concat_folder_components = folder.components + folder.flows

        flows_ids = session.exec(select(Flow.id).where(Flow.folder_id == existing_folder.id)).all()

        excluded_flows = list(set(flows_ids) - set(concat_folder_components))

        my_collection_folder = session.exec(select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME)).first()
        if my_collection_folder:
            update_statement_my_collection = (
                update(Flow).where(Flow.id.in_(excluded_flows)).values(folder_id=my_collection_folder.id)  # type: ignore[attr-defined]
            )
            session.exec(update_statement_my_collection)
            session.commit()

        if concat_folder_components:
            update_statement_components = (
                update(Flow).where(Flow.id.in_(concat_folder_components)).values(folder_id=existing_folder.id)  # type: ignore[attr-defined]
            )
            session.exec(update_statement_components)
            session.commit()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return existing_folder


@router.delete("/{folder_id}", status_code=204)
def delete_folder(
    *,
    session: DbSession,
    folder_id: str,
    current_user: CurrentActiveUser,
):
    try:
        flows = session.exec(select(Flow).where(Flow.folder_id == folder_id, Flow.user_id == current_user.id)).all()
        if len(flows) > 0:
            for flow in flows:
                cascade_delete_flow(session, flow)

        folder = session.exec(select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id)).first()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    try:
        session.delete(folder)
        session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/download/{folder_id}", response_model=FlowListReadWithFolderName, status_code=200)
async def download_file(
    *,
    session: DbSession,
    folder_id: str,
    current_user: CurrentActiveUser,
):
    """Download all flows from folder."""
    try:
        folder = session.exec(select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id)).first()
    except Exception as e:
        if "No result found" in str(e):
            raise HTTPException(status_code=404, detail="Folder not found") from e
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    return folder


@router.post("/upload/", response_model=list[FlowRead], status_code=201)
async def upload_file(
    *,
    session: DbSession,
    file: Annotated[UploadFile, File(...)],
    current_user: CurrentActiveUser,
):
    """Upload flows from a file."""
    contents = await file.read()
    data = orjson.loads(contents)

    if not data:
        raise HTTPException(status_code=400, detail="No flows found in the file")

    folder_name = generate_unique_folder_name(data["folder_name"], current_user.id, session)

    data["folder_name"] = folder_name

    folder = FolderCreate(name=data["folder_name"], description=data["folder_description"])

    new_folder = Folder.model_validate(folder, from_attributes=True)
    new_folder.id = None
    new_folder.user_id = current_user.id
    session.add(new_folder)
    session.commit()
    session.refresh(new_folder)

    del data["folder_name"]
    del data["folder_description"]

    if "flows" in data:
        flow_list = FlowListCreate(flows=[FlowCreate(**flow) for flow in data["flows"]])
    else:
        raise HTTPException(status_code=400, detail="No flows found in the data")
    # Now we set the user_id for all flows
    for flow in flow_list.flows:
        flow_name = generate_unique_flow_name(flow.name, current_user.id, session)
        flow.name = flow_name
        flow.user_id = current_user.id
        flow.folder_id = new_folder.id

    return create_flows(session=session, flow_list=flow_list, current_user=current_user)
