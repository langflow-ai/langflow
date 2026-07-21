"""Names shared between the runtime's application telemetry and the exporter that ships it.

Application observability answers whether the service is healthy: request rates, latency,
errors, and the units of work the service performed. It is a separate concern from the LLM
tracer integrations, which describe what a flow did and carry prompt and completion text.

This lives in lfx because the spans are emitted from the graph, which lfx owns, while the
tracer provider and its export filter live in langflow. lfx cannot import langflow, so the
name they must agree on belongs here.
"""

# The tracer name Langflow's own application spans are emitted under. Deliberately not
# "langflow": the LLM tracer integrations already take a tracer under that name, and their
# spans carry flow inputs and outputs. langflow's export filter allowlists this exact
# string, so a span emitted under any other name never reaches the operator's APM.
APPLICATION_TRACER_NAME = "langflow.observability"
