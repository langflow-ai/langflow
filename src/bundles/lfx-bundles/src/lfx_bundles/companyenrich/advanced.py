from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, DictInput, DropdownInput
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.companyenrich._catalog import OPERATIONS
from lfx_bundles.companyenrich._client import connection_inputs, execute


class CompanyEnrichAdvancedComponent(Component):
    display_name = "Advanced CompanyEnrich Request"
    description = (
        "One of 42 approved operations. Email operations are beta. No automatic retries, polling or downloads."
    )
    icon = "CompanyEnrich"
    name = "CompanyEnrichAdvanced"
    inputs = [
        *connection_inputs(),
        DropdownInput(name="operation", display_name="Operation", options=list(OPERATIONS), value="get_industries"),
        DictInput(name="body", display_name="Body", advanced=True),
        DictInput(name="query_parameters", display_name="Query Parameters", advanced=True),
        DictInput(name="path_parameters", display_name="Path Parameters", advanced=True),
        BoolInput(name="allow_beta", display_name="Allow Beta Email Operations", value=False, advanced=True),
    ]
    outputs = [Output(display_name="Result", name="result", method="call_operation")]

    async def call_operation(self) -> Data:
        return await execute(
            self,
            self.operation,
            body=self.body,
            query=self.query_parameters,
            path_parameters=self.path_parameters,
            allow_beta=self.allow_beta,
        )
