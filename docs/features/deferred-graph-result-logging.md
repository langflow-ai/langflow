# Deferred graph result logging

Completed-task debug logging in `Graph._execute_tasks` passes the result and
built object through the logger's positional formatting interface. Structlog's
configured filtering logger checks the level before interpolating those values.
The global log level, processors, and other graph logging remain unchanged.

At INFO, a result's representation methods no longer run just to construct a
message that will be discarded. Their side effects and exceptions are therefore
intentionally absent on that disabled path. DEBUG still renders values; a
representation failure keeps the existing failure boundary after result
recording and runnable removal, before successor handling/event emission.

Tests cover scalar, nested, observed, and pandas dataframe representations,
context propagation, task ordering, and exceptions. Authenticated backend tests
compare normalized run responses, build events and SQLite messages using a
controlled restoration of the old f-string at the same call site. Generated
IDs and timestamps are also normalized inside intermediate history tables.

The measured no-LLM `/run` flow reaches this method; the build/event path in that
fixture does not. Neither helper speedups nor unaffected build timings establish
a production endpoint improvement. `scripts/benchmark/graph_result_logging.py`
reports INFO and DEBUG samples separately for scalars, nested mappings and
200-by-8 dataframes. Use `LANGFLOW_LOGGING_BENCHMARK_PAIRS=20` with pytest `-s`
on `test_result_logging_request_parity.py` to repeat request measurements.
