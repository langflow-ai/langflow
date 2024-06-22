from typing import Optional, Any, List
from pydantic import BaseModel


class ResultPair(BaseModel):
    result: Any
    extra: Any


class Payload(BaseModel):
    result_pairs: List[ResultPair] = []

    def __iter__(self):
        return iter(self.result_pairs)

    def add_result_pair(self, result: Any, extra: Optional[Any] = None) -> None:
        self.result_pairs.append(ResultPair(result=result, extra=extra))

    def get_last_result_pair(self) -> ResultPair:
        return self.result_pairs[-1]

    # format all but the last result pair
    # into a string
    def format(self, sep: str = "\n") -> str:
        # Result: the result
        # Extra: the extra if it exists don't show if it doesn't
        return sep.join(
            [
                f"Result: {result_pair.result}\nExtra: {result_pair.extra}"
                if result_pair.extra is not None
                else f"Result: {result_pair.result}"
                for result_pair in self.result_pairs[:-1]
            ]
        )
