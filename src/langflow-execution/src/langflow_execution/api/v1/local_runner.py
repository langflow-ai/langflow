import logging

logger = logging.getLogger(__name__)

class DefaultFlowRunner:
    async def run(
        self,
        *,
        input_request: FlowExecutionRequest,
        flow: Flow,
    ) -> FlowExecutionResponse | StreamingResponse:

        """
        Execute a flow with the given input request.
        Args:
            input_request: The request containing flow execution parameters.
        Returns:
            The result of the flow execution (type depends on implementation).
        """



