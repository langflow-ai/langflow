from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional
from sqlmodel import SQLModel, Session


T = TypeVar("T", bound=SQLModel)


class AbstractRepository(ABC, Generic[T]):
    def __init__(self, session: Session):
        self.session = session

    @abstractmethod
    def add(self, entity: T) -> T:
        pass

    @abstractmethod
    def get(self, id: int) -> Optional[T]:
        pass

    @abstractmethod
    def list(self) -> List[T]:
        pass

    @abstractmethod
    def update(self, entity: T) -> T:
        pass

    @abstractmethod
    def delete(self, id: int) -> None:
        pass
