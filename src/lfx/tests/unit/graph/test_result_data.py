import threading

from lfx.graph.schema import ResultData


def test_result_data_ignores_non_dict_artifact_values():
    """Vector DB artifacts may include non-iterable objects such as locks."""
    lock = threading.Lock()

    result = ResultData(artifacts={"vector_db": lock})

    assert result.artifacts == {"vector_db": lock}
    assert result.outputs == {}
