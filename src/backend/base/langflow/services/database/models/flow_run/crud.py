from uuid import UUID
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, delete
from .model import FlowRun

async def create_flow_run(db: AsyncSession, flow_id: UUID) -> FlowRun:
    run = FlowRun(flow_id=flow_id)
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run

async def update_flow_run_status(db: AsyncSession, run_id: UUID, status: str, result: dict = None, error: str = None):
    stmt = select(FlowRun).where(FlowRun.id == run_id)
    res = await db.exec(stmt)
    run = res.one()
    run.status = status
    if result is not None:
        run.result = result
    if error is not None:
        run.error = error
    await db.commit()
    await db.refresh(run)
    return run

async def get_flow_run(db: AsyncSession, run_id: UUID) -> FlowRun:
    stmt = select(FlowRun).where(FlowRun.id == run_id)
    res = await db.exec(stmt)
    return res.one()

async def delete_flow_run(db: AsyncSession, run_id: UUID) -> None:
    stmt = delete(FlowRun).where(FlowRun.id == run_id)
    await db.exec(stmt)
    await db.commit()

async def list_flow_runs(db: AsyncSession) -> list[FlowRun]:
    stmt = select(FlowRun).order_by(FlowRun.created_at.desc())
    res = await db.exec(stmt)
    return res.all()
