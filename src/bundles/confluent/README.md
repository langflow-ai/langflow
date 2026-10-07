# lfx-confluent

[IBM Confluent](https://www.ibm.com/products/confluent) — the data-in-motion
half of IBM's streaming lakehouse — as a standalone Langflow Extension
Bundle. Everything talks to Confluent over open protocols only (Kafka wire
protocol, the Tableflow Iceberg REST catalog, and MCP over Streamable HTTP),
so the same components work against Confluent Cloud, Confluent Platform, and
WarpStream wherever the corresponding surface is exposed.

## What it ships

Four components, registered under the `confluent` bundle group:

- **Confluent Real-Time Context Engine** (`ConfluentContextEngineComponent`,
  canonical ID `ext:confluent:ConfluentContextEngineComponent@official`) — a
  preset MCP toolset for Confluent's Real-Time Context Engine. Templates the
  regional MCP endpoint from your organization / environment / cluster IDs,
  authenticates with a Confluent Cloud API key, and exposes `list_topics`,
  `get_metadata`, and `query_data` to an **Agent** (Tool Mode) or runs one
  tool directly (Response output).
- **Confluent Kafka Producer** (`ConfluentKafkaProducerComponent`) — publish
  a Message, a Data object, or every row of a DataFrame to a topic and return
  the delivery report.
- **Confluent Kafka Consumer** (`ConfluentKafkaConsumerComponent`) — read a
  bounded batch of records (message limit + timeout) into a DataFrame; JSON,
  string, Avro, and JSON-Schema (Schema Registry) values.
- **Confluent Tableflow Reader** (`ConfluentTableflowReaderComponent`) — read
  a Kafka topic that Tableflow has materialized as an Apache Iceberg table
  through the Tableflow Iceberg REST catalog (`pyiceberg`, no JVM), with a
  row filter, projection, and row limit; or list the tables in a cluster.

Built on [`confluent-kafka`](https://pypi.org/project/confluent-kafka/) and
[`pyiceberg`](https://pypi.org/project/pyiceberg/); the MCP component reuses
Langflow's own MCP client engine.

## Install

```bash
pip install lfx-confluent
```

`pip install "langflow[bundles]"` also includes it.

## Develop

The bundle is a uv workspace member of the Langflow monorepo:

```bash
uv sync
uv run pytest src/bundles/confluent/tests -q
uv run lfx extension validate src/bundles/confluent/src/lfx_confluent
```

To iterate on the components with a live palette:

```bash
uv run lfx extension dev src/bundles/confluent
```

Live smoke tests (marked `api_key_required`) need a Confluent Cloud
environment; see the test module docstrings for the environment variables
they read.
