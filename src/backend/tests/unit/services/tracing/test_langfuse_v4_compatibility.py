"""Regression tests for the Langfuse v4 tracing integration."""

import contextlib
import os
import sys
import types
import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def langfuse_env_vars():
    with patch.dict(
        os.environ,
        {
            "LANGFUSE_SECRET_KEY": "sk-lf-test",  # pragma: allowlist secret
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_HOST": "http://localhost:3000",
        },
    ):
        yield


@pytest.fixture(autouse=True)
def reset_langfuse_shared_client():
    from langflow.services.tracing.langfuse import _reset_shared_client_for_tests

    _reset_shared_client_for_tests()
    yield
    _reset_shared_client_for_tests()


class _FakeLangchainCallbackHandler:
    def __init__(self, *, trace_context=None, **kwargs):  # noqa: ARG002
        self.run_inline = True
        self.trace_context = trace_context

    def on_chat_model_start(self, *args, **kwargs):  # noqa: ARG002
        return None

    def on_llm_start(self, *args, **kwargs):  # noqa: ARG002
        return None


@pytest.fixture
def mock_langfuse():
    class TraceContext(dict):
        pass

    @contextmanager
    def propagation_context(**kwargs):  # noqa: ARG001
        yield

    langfuse_module = types.ModuleType("langfuse")
    langfuse_types_module = types.ModuleType("langfuse.types")
    langfuse_langchain_module = types.ModuleType("langfuse.langchain")
    langfuse_class = MagicMock()
    client = MagicMock()
    root_observation = MagicMock()
    child_observation = MagicMock()

    langfuse_types_module.TraceContext = TraceContext
    langfuse_langchain_module.CallbackHandler = _FakeLangchainCallbackHandler
    langfuse_module.Langfuse = langfuse_class
    langfuse_module.propagate_attributes = MagicMock(side_effect=propagation_context)
    langfuse_module.types = langfuse_types_module
    langfuse_module.langchain = langfuse_langchain_module
    langfuse_class.return_value = client
    langfuse_class.create_trace_id = MagicMock(return_value="a" * 32)
    client.auth_check.return_value = True
    client.api = types.SimpleNamespace(
        legacy=types.SimpleNamespace(score_v1=types.SimpleNamespace(delete=MagicMock())),
        scores=object(),
    )
    client.start_observation.return_value = root_observation
    root_observation.id = "b" * 16
    root_observation.start_observation.return_value = child_observation
    child_observation.id = "c" * 16

    with patch.dict(
        sys.modules,
        {
            "langfuse": langfuse_module,
            "langfuse.types": langfuse_types_module,
            "langfuse.langchain": langfuse_langchain_module,
        },
    ):
        yield {
            "client": client,
            "langfuse_class": langfuse_class,
            "root": root_observation,
            "propagate": langfuse_module.propagate_attributes,
        }


class TestLangfuseV4Api:
    def test_sdk_exposes_v4_observation_api(self):
        from langfuse import Langfuse, propagate_attributes

        assert hasattr(Langfuse, "start_observation")
        assert hasattr(Langfuse, "start_as_current_observation")
        assert callable(propagate_attributes)


class TestLangfuseTracerV4:
    @pytest.mark.parametrize("completion_order", [("a", "b"), ("b", "a")])
    def test_callback_sibling_completion_restores_context_in_either_order(self, completion_order):
        from langflow.services.tracing.langfuse import _langchain_handler_cls
        from lfx.services.tracing.base import callback_invocation_scope
        from opentelemetry import context, trace
        from opentelemetry.context import _RUNTIME_CONTEXT

        class BaseHandler:
            def __init__(self, **kwargs):  # noqa: ARG002
                self.tokens = {}

            def _attach_observation(self, run_id, observation):
                self.tokens[run_id] = context.attach(trace.set_span_in_context(observation._otel_span))

            def _detach_observation(self, run_id):
                with contextlib.suppress(Exception):
                    _RUNTIME_CONTEXT.detach(self.tokens.pop(run_id))

        class Observation:
            _otel_span = trace.INVALID_SPAN

        handler = _langchain_handler_cls(BaseHandler)(trace_attributes={"user_id": "sync-user"})
        initial = context.get_current()
        runs = {name: uuid.uuid4() for name in ("a", "b")}
        with callback_invocation_scope([handler]):
            handler._attach_observation(runs["a"], Observation())
            handler._attach_observation(runs["b"], Observation())
            assert context.get_value("langfuse.propagated.user_id") == "sync-user"
            for name in completion_order:
                handler._detach_observation(runs[name])
        assert context.get_current() is initial

    def test_vendor_session_normalization_preserves_short_and_hashes_invalid_ids(self):
        from langflow.services.tracing.langfuse import LangFuseTracer

        short = "session-short"
        long_a = "a" * 201
        long_b = "b" * 201
        non_ascii = "sessión"
        for session_id in (short, long_a, long_b, non_ascii):
            tracer = LangFuseTracer(
                trace_name="test-flow - flow-123",
                trace_type="chain",
                project_name="test-project",
                trace_id=uuid.uuid4(),
                session_id=session_id,
            )
            vendor_id = tracer._attributes()["session_id"]
            if session_id == short:
                assert vendor_id == short
            else:
                assert vendor_id.startswith("langflow-session-")
                assert len(vendor_id) <= 200
                assert vendor_id.isascii()
        assert (
            LangFuseTracer(
                "test-flow - flow-123", "chain", "test-project", uuid.uuid4(), session_id=long_a
            )._attributes()["session_id"]
            == LangFuseTracer(
                "test-flow - flow-123", "chain", "test-project", uuid.uuid4(), session_id=long_a
            )._attributes()["session_id"]
        )

    def test_observation_attributes_isolate_ambient_flow_and_restore_caller(self):
        from langflow.services.tracing.langfuse import LangFuseTracer
        from langfuse import propagate_attributes
        from langfuse._client.propagation import _get_propagated_attributes_from_context
        from opentelemetry import context

        tracer = LangFuseTracer.__new__(LangFuseTracer)
        tracer.user_id = None
        tracer.session_id = None
        tracer._trace_metadata = {"flow_id": "flow-b"}
        tracer.flow_display_name = "flow-b"
        caller = context.get_current()
        with propagate_attributes(user_id="flow-a-user", session_id="flow-a-session", metadata={"flow_id": "flow-a"}):
            with tracer._observation_attributes():
                propagated = _get_propagated_attributes_from_context(context.get_current())
                assert "user.id" not in propagated
                assert "session.id" not in propagated
                assert propagated["langfuse.trace.metadata.flow_id"] == "flow-b"
            assert context.get_current() is not caller
            assert _get_propagated_attributes_from_context(context.get_current())["user.id"] == "flow-a-user"
        assert context.get_current() is caller

    def test_invocation_scope_restores_caller_context(self):
        from langflow.services.tracing.langfuse import LangFuseTracer
        from langfuse._client.propagation import _get_propagated_attributes_from_context
        from opentelemetry import context, trace

        tracer = LangFuseTracer.__new__(LangFuseTracer)
        tracer.user_id = "user-b"
        tracer.session_id = "session-b"
        tracer._trace_metadata = {"flow_id": "flow-b"}
        tracer.flow_display_name = "flow-b"
        caller = context.get_current()
        with tracer.langflow_invocation_scope():
            assert trace.get_current_span() is trace.INVALID_SPAN
            propagated = _get_propagated_attributes_from_context(context.get_current())
            assert propagated["user.id"] == "user-b"
            assert propagated["session.id"] == "session-b"
        assert context.get_current() is caller

    def test_shared_client_is_reused_for_multiple_flow_runs(self, mock_langfuse):
        from langflow.services.tracing.langfuse import LangFuseTracer

        tracers = [
            LangFuseTracer(
                trace_name="test-flow - flow-123",
                trace_type="chain",
                project_name="test-project",
                trace_id=uuid.uuid4(),
            )
            for _ in range(2)
        ]

        assert mock_langfuse["langfuse_class"].call_count == 1
        assert tracers[0]._client is tracers[1]._client

    def test_credential_rotation_creates_a_new_shared_client(self, mock_langfuse):
        from langflow.services.tracing.langfuse import LangFuseTracer

        LangFuseTracer(
            trace_name="test-flow - flow-123",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
        )

        with patch.dict(
            os.environ,
            {
                "LANGFUSE_SECRET_KEY": "sk-lf-rotated",  # pragma: allowlist secret
                "LANGFUSE_PUBLIC_KEY": "pk-lf-rotated",
            },
        ):
            LangFuseTracer(
                trace_name="test-flow - flow-456",
                trace_type="chain",
                project_name="test-project",
                trace_id=uuid.uuid4(),
            )

        assert mock_langfuse["langfuse_class"].call_count == 2
        first_config = mock_langfuse["langfuse_class"].call_args_list[0].kwargs
        second_config = mock_langfuse["langfuse_class"].call_args_list[1].kwargs
        assert first_config["secret_key"] != second_config["secret_key"]
        assert first_config["public_key"] != second_config["public_key"]

    def test_shared_client_uses_an_isolated_tracer_provider(self, mock_langfuse):
        from langflow.services.tracing.langfuse import LangFuseTracer
        from opentelemetry.sdk.trace import TracerProvider

        LangFuseTracer(
            trace_name="test-flow - flow-123",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
        )

        provider = mock_langfuse["langfuse_class"].call_args.kwargs["tracer_provider"]
        assert isinstance(provider, TracerProvider)

    def test_initializes_root_observation_with_propagated_attributes(self, mock_langfuse):
        from langflow.services.tracing.langfuse import LangFuseTracer

        tracer = LangFuseTracer(
            trace_name="test-flow - flow-123",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
            user_id="auth-user",
            session_id="session-1",
            tracing_user_id="end-user-456",
        )

        assert tracer.ready
        root_kwargs = mock_langfuse["client"].start_observation.call_args.kwargs
        assert root_kwargs["as_type"] == "span"
        assert root_kwargs["name"] == "test-flow"

        propagation_kwargs = mock_langfuse["propagate"].call_args.kwargs
        assert propagation_kwargs["user_id"] == "auth-user"
        assert propagation_kwargs["session_id"] == "session-1"
        assert propagation_kwargs["trace_name"] == "test-flow"
        assert propagation_kwargs["metadata"]["langflow.tracing_user_id"] == "end-user-456"

    def test_child_observation_uses_v4_api_and_propagates_trace_attributes(self, mock_langfuse):
        from langflow.services.tracing.langfuse import LangFuseTracer

        tracer = LangFuseTracer(
            trace_name="test-flow - flow-123",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
        )
        tracer.add_trace(
            trace_id="component-1",
            trace_name="TestComponent (component-1)",
            trace_type="llm",
            inputs={"prompt": "test"},
        )

        child_kwargs = mock_langfuse["root"].start_observation.call_args.kwargs
        assert child_kwargs["as_type"] == "span"
        assert child_kwargs["name"] == "TestComponent"
        assert mock_langfuse["propagate"].call_count == 2

    def test_end_updates_and_ends_root_observation(self, mock_langfuse):
        from langflow.services.tracing.langfuse import LangFuseTracer

        tracer = LangFuseTracer(
            trace_name="test-flow - flow-123",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
        )
        tracer.end(inputs={"input": "hello"}, outputs={"output": "world"}, metadata={"final": True})

        update_kwargs = mock_langfuse["root"].update.call_args.kwargs
        assert update_kwargs["input"] == {"input": {"input": "hello"}}
        assert update_kwargs["output"] == {"output": {"output": "world"}}
        assert update_kwargs["metadata"] == {"final": True}
        mock_langfuse["root"].set_trace_io.assert_called_once_with(
            input={"input": {"input": "hello"}},
            output={"output": {"output": "world"}},
        )
        mock_langfuse["root"].end.assert_called_once()
        mock_langfuse["client"].flush.assert_called_once()

    def test_end_preserves_marked_graph_boundary_values(self, mock_langfuse):
        from langflow.services.tracing.langfuse import LangFuseTracer

        tracer = LangFuseTracer(
            trace_name="test-flow - flow-123",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
        )
        tracer.add_trace(
            trace_id="input-id",
            trace_name="Chat Input (input-id)",
            trace_type="chain",
            inputs={"text": "request"},
            vertex=types.SimpleNamespace(is_input=True, is_output=False),
        )
        tracer.add_trace(
            trace_id="output-id",
            trace_name="Chat Output (output-id)",
            trace_type="chain",
            inputs={},
            vertex=types.SimpleNamespace(is_input=False, is_output=True),
        )

        tracer.end(
            inputs={"Chat Input (input-id)": {"text": "request"}},
            outputs={"Chat Input (input-id)": {"text": "request"}, "Chat Output (output-id)": "response"},
        )

        update_kwargs = mock_langfuse["root"].update.call_args.kwargs
        assert update_kwargs["input"] == {"input": "request"}
        assert update_kwargs["output"] == {"output": "response"}
        mock_langfuse["root"].set_trace_io.assert_called_once_with(
            input={"input": "request"}, output={"output": "response"}
        )

    def test_setup_errors_are_visible(self):
        from langflow.services.tracing.langfuse import LangFuseTracer

        with (
            patch("langfuse.Langfuse") as langfuse_class,
            patch("langflow.services.tracing.langfuse.logger") as logger,
        ):
            langfuse_class.create_trace_id = MagicMock(return_value="a" * 32)
            client = MagicMock()
            client.auth_check.return_value = True
            client.start_observation.side_effect = RuntimeError("setup failed")
            langfuse_class.return_value = client

            tracer = LangFuseTracer(
                trace_name="test - flow-1",
                trace_type="chain",
                project_name="proj",
                trace_id=uuid.uuid4(),
            )

        assert tracer.ready is False
        logger.exception.assert_called_once()

    def test_feedback_deletion_uses_v4_legacy_score_endpoint(self, mock_langfuse):
        from langflow.services.tracing.langfuse import delete_feedback_score

        message_id = uuid.uuid4()
        delete_feedback_score(message_id=message_id)

        mock_langfuse["client"].api.legacy.score_v1.delete.assert_called_once_with(score_id=message_id.hex)
