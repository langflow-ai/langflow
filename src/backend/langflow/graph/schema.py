from typing import Any, List
from pydantic import BaseModel


class ResultPair(BaseModel):
    result: Any
    extra: Any


class GraphInput(BaseModel):
    result_pairs: List[ResultPair] = []

    def __iter__(self):
        return iter(self.result_pairs)

    def add_result_pair(self, result: Any, extra: Any = None) -> None:
        self.result_pairs.append(ResultPair(result=result, extra=extra))

    def get_last_result_pair(self) -> ResultPair:
        return self.result_pairs[-1]
