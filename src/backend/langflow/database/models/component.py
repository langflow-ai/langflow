from langflow.database.models.base import SQLModelSerializable
from sqlmodel import Field
from typing import Optional
from datetime import datetime
import uuid

# def orjson_dumps(v, *, default):
#     # orjson.dumps returns bytes, to match standard json.dumps we need to decode
#     return orjson.dumps(v, default=default).decode()

# class SQLModelSerializable(SQLModel):
#     class Config:
#         orm_mode = True
#         json_loads = orjson.loads
#         json_dumps = orjson_dumps

# DATABASE_URL = "sqlite+pysqlite:///./database.db"

# engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)


class Component(SQLModelSerializable, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    id_frontend_node: uuid.UUID = Field(index=True)
    name: str = Field(index=True)
    description: Optional[str] = Field(index=True)
    code_python: Optional[str] = Field(default=None)
    return_type: Optional[str] = Field(index=True)
    create_at: datetime = Field(default_factory=datetime.utcnow)
    update_at: datetime = Field(default_factory=datetime.utcnow)
    is_disabled: bool = Field(default=False)
    is_read_only: bool = Field(default=False)


# app = FastAPI()

# def get_db():
#     with Session(engine) as session:
#         yield session

# @app.on_event("startup")
# def on_startup():
#     SQLModel.metadata.create_all(engine)

# @app.post("/components/", response_model=Component)
# def create_component(component: Component, db: Session = Depends(get_db)):
#     db.add(component)
#     db.commit()
#     db.refresh(component)
#     return component

# @app.get("/components/{component_id}", response_model=Component)
# def read_component(component_id: uuid.UUID, db: Session = Depends(get_db)):
#     component = db.get(Component, component_id)
#     if not component:
#         raise HTTPException(status_code=404, detail="Component not found")
#     return component

# @app.get("/components/", response_model=List[Component])
# def read_components(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
#     components = db.execute(select(Component).offset(skip).limit(limit)).fetchall()
#     return components

# @app.put("/components/{component_id}", response_model=Component)
# def update_component(component_id: uuid.UUID, component: Component, db: Session = Depends(get_db)):
#     db_component = db.get(Component, component_id)
#     if not db_component:
#         raise HTTPException(status_code=404, detail="Component not found")
#     component_data = component.dict(exclude_unset=True)
#     for key, value in component_data.items():
#         setattr(db_component, key, value)
#     db.commit()
#     db.refresh(db_component)
#     return db_component

# @app.delete("/components/{component_id}")
# def delete_component(component_id: uuid.UUID, db: Session = Depends(get_db)):
#     component = db.get(Component, component_id)
#     if not component:
#         raise HTTPException(status_code=404, detail="Component not found")
#     db.delete(component)
#     db.commit()
#     return {"detail": "Component deleted"}
