from typing import List, Optional
from sqlmodel import select
from langflow.services.database.models.variable import Variable
from langflow.services.database.models.repo import AbstractRepository


class VariableRepository(AbstractRepository):
    def add(self, entity: Variable) -> Variable:
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def get(self, id: int) -> Optional[Variable]:
        return self.session.get(Variable, id)

    def list(self) -> List[Variable]:
        query = select(Variable)
        return list(self.session.exec(query).all())

    def update(self, entity: Variable) -> Variable:
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def delete(self, id: int) -> None:
        entity = self.get(id)
        if entity:
            self.session.delete(entity)
            self.session.commit()
