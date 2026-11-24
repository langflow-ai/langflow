"""lfx-confluent: IBM Confluent bundle (data-in-motion side of the IBM streamhouse).

This package is the distribution unit ``lfx-confluent``.  At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers the components under the namespaced IDs:

* ``ext:confluent:ConfluentContextEngineComponent@official``
* ``ext:confluent:ConfluentKafkaConsumerComponent@official``
* ``ext:confluent:ConfluentKafkaProducerComponent@official``
* ``ext:confluent:ConfluentTableflowReaderComponent@official``

Everything talks to Confluent over open protocols only -- the Kafka wire
protocol (``confluent-kafka``), the Tableflow Iceberg REST catalog
(``pyiceberg``), and MCP over Streamable HTTP (Langflow's own MCP client
engine) -- so the same components work against Confluent Cloud, Confluent
Platform, and WarpStream wherever the corresponding surface is exposed.
"""

from lfx_confluent.components.confluent.context_engine import ConfluentContextEngineComponent
from lfx_confluent.components.confluent.kafka_consumer import ConfluentKafkaConsumerComponent
from lfx_confluent.components.confluent.kafka_producer import ConfluentKafkaProducerComponent
from lfx_confluent.components.confluent.tableflow_reader import ConfluentTableflowReaderComponent

__all__ = [
    "ConfluentContextEngineComponent",
    "ConfluentKafkaConsumerComponent",
    "ConfluentKafkaProducerComponent",
    "ConfluentTableflowReaderComponent",
]
