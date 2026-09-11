from langflow.utils import connection_string_parser as langflow_parser
from lfx.utils import connection_string_parser as lfx_parser


def test_langflow_reexports_lfx_helper():
    """The langflow module is a shim; behavior is tested in src/lfx/tests/unit/utils."""
    assert langflow_parser.transform_connection_string is lfx_parser.transform_connection_string
    assert langflow_parser.transform_connection_string("protocol:user:p/ss@host") == "protocol:user:p%2Fss@host"
