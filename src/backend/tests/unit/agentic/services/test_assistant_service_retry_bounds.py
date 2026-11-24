"""execute_flow_with_validation retry-loop boundary.

Bug: with ``max_retries < 0`` the ``while attempt <= max_retries`` loop
never executes a single attempt, so ``result`` / ``validation`` are never
bound. The post-loop "safety return" then referenced those unbound
locals, crashing with ``UnboundLocalError`` instead of returning a
domain-meaningful error.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.services.assistant_service import execute_flow_with_validation

MODULE = "langflow.agentic.services.assistant_service"


class TestRetryLoopBoundary:
    @pytest.mark.asyncio
    async def test_should_return_domain_error_when_max_retries_is_negative(self):
        # max_retries=-1 → the loop body never runs (no attempt made).
        mock_execute = AsyncMock()
        with patch(f"{MODULE}.execute_flow_file", mock_execute):
            result = await execute_flow_with_validation(
                flow_filename="TestFlow",
                input_value="create a component that adds two numbers",
                global_variables={},
                max_retries=-1,
            )

        # Must NOT crash with UnboundLocalError; no flow attempt was made.
        mock_execute.assert_not_called()
        assert result["validated"] is False
        assert result["validation_attempts"] == 0
        assert "result" in result
