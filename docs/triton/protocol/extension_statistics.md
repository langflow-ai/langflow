<!--
# Copyright 2020-2023, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#  * Neither the name of NVIDIA CORPORATION nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
# OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
-->

# Statistics Extension

This document describes Triton's statistics extension. The statistics
extension enables the reporting of per-model (per-version) statistics
which provide aggregate information about all activity occurring for a
specific model (version) since Triton started. Because this extension
is supported, Triton reports “statistics” in the extensions field of
its Server Metadata.

## HTTP/REST

In all JSON schemas shown in this document `$number`, `$string`, `$boolean`,
`$object` and `$array` refer to the fundamental JSON types. #optional
indicates an optional JSON field.

Triton exposes the statistics endpoint at the following URL. The
specific model name portion of the URL is optional; if not provided
Triton will return the statistics for all versions of all models. If a
specific model is given in the URL the versions portion of the URL is
optional; if not provided Triton will return statistics for all
versions of the specified model.

```
GET v2/models[/${MODEL_NAME}[/versions/${MODEL_VERSION}]]/stats
```

### Statistics Response JSON Object

A successful statistics request is indicated by a 200 HTTP status
code. The response object, identified as `$stats_model_response`, is
returned in the HTTP body for every successful statistics request.

```
$stats_model_response =
{
  "model_stats" : [ $model_stat, ... ]
}
```

Each `$model_stat` object gives the statistics for a specific model and
version. The `$version` field is optional for servers that do not
support versions.

```
$model_stat =
{
  "name" : $string,
  "version" : $string #optional,
  "last_inference" : $number,
  "inference_count" : $number,
  "execution_count" : $number,
  "inference_stats" : $inference_stats,
  "response_stats" : { $string : $response_stats, ... },
  "batch_stats" : [ $batch_stats, ... ],
  "memory_usage" : [ $memory_usage, ...]
}
```

- "name" : The name of the model.

- "version" : The version of the model.

- "last_inference" : The timestamp of the last inference request made
  for this model, as milliseconds since the epoch.

- "inference_count" : The cumulative count of successful inference
  requests made for this model. Each inference in a batched request is
  counted as an individual inference. For example, if a client sends a
  single inference request with batch size 64, "inference_count" will
  be incremented by 64. Similarly, if a clients sends 64 individual
  requests each with batch size 1, "inference_count" will be
  incremented by 64. The "inference_count" value DOES NOT include cache hits.

- "execution_count" : The cumulative count of the number of successful
  inference executions performed for the model. When dynamic batching
  is enabled, a single model execution can perform inferencing for
  more than one inference request. For example, if a clients sends 64
  individual requests each with batch size 1 and the dynamic batcher
  batches them into a single large batch for model execution then
  "execution_count" will be incremented by 1. If, on the other hand,
  the dynamic batcher is not enabled for that each of the 64
  individual requests is executed independently, then
  "execution_count" will be incremented by 64. The "execution_count" value
  DOES NOT include cache hits.

- "inference_stats" : The aggregate statistics for the
  model. So, for example, "inference_stats":"success" indicates the number of
  successful inference requests for the model.

- "response_stats" : The aggregate response statistics for the model. For
  example, { "key" : { "response_stats" : "success" } } indicates the aggregate
  statistics of successful responses at "key" for the model, where "key"
  identifies each response generated by the model across different requests. For
  example, given a model that generates three responses, the keys can be "0",
  "1" and "2" identifying the three responses in order.

- "batch_stats" : The aggregate statistics for each different batch
  size that is executed in the model. The batch statistics indicate
  how many actual model executions were performed and show differences
  due to different batch size (for example, larger batches typically
  take longer to compute).

- "memory_usage" : The memory usage detected during model loading, which may be
  used to estimate the memory to be released once the model is unloaded. Note
  that the estimation is inferenced by the profiling tools and framework's
  memory schema, therefore it is advised to perform experiments to understand
  the scenario that the reported memory usage can be relied on. As a starting
  point, the GPU memory usage for models in ONNX Runtime backend and TensorRT
  backend is usually aligned.

```
$inference_stats =
{
  "success" : $duration_stat,
  "fail" : $duration_stat,
  "queue" : $duration_stat,
  "compute_input" : $duration_stat,
  "compute_infer" : $duration_stat,
  "compute_output" : $duration_stat,
  "cache_hit": $duration_stat,
  "cache_miss": $duration_stat
}
```

- “success” : The count and cumulative duration for all successful
  inference requests. The "success" count and cumulative duration includes
  cache hits.

- “fail” : The count and cumulative duration for all failed inference
  requests.

- “queue” : The count and cumulative duration that inference requests
  wait in scheduling or other queues. The "queue" count and cumulative
  duration includes cache hits.

- “compute_input” : The count and cumulative duration to prepare input
  tensor data as required by the model framework / backend. For
  example, this duration should include the time to copy input tensor
  data to the GPU. The "compute_input" count and cumulative duration DO NOT
  include cache hits.

- “compute_infer” : The count and cumulative duration to execute the
  model. The "compute_infer" count and cumulative duration DO NOT include
  cache hits.

- “compute_output” : The count and cumulative duration to extract
  output tensor data produced by the model framework / backend. For
  example, this duration should include the time to copy output tensor
  data from the GPU. The "compute_output" count and cumulative duration DO NOT
  include cache hits.

- "cache_hit" : The count of response cache hits and cumulative duration to
  lookup and extract output tensor data from the Response Cache on a cache hit.
  For example, this duration should include the time to copy output tensor data
  from the Response Cache to the response object.

- "cache_miss" : The count of response cache misses and cumulative duration to
  lookup and insert output tensor data to the Response Cache on a cache miss.
  For example, this duration should include the time to copy output tensor data
  from the response object to the Response Cache.


```
$response_stats =
{
  "compute_infer" : $duration_stat,
  "compute_output" : $duration_stat,
  "success" : $duration_stat,
  "fail" : $duration_stat,
  "empty_response" : $duration_stat,
  "cancel" : $duration_stat
}
```

- "compute_infer" : The count and cumulative duration to compute a response.
- "compute_output" : The count and cumulative duration to extract the output
  tensor of a computed response.
- "success" : The count and cumulative duration of a success inference. The
  duration is the sum of infer and output durations.
- "fail" : The count and cumulative duration of a fail inference. The duration
  is the sum of infer and output durations.
- "empty_response" : The count and cumulative duration of an inference with an
  empty / no response. The duration is infer durations.
- "cancel" : The count and cumulative duration of a inference cancellation. The
  duration is for cleaning up resources held by cancelled inference requests.


```
$batch_stats =
{
  "batch_size" : $number,
  "compute_input" : $duration_stat,
  "compute_infer" : $duration_stat,
  "compute_output" : $duration_stat
}
```

- "batch_size" : The size of the batch.

- "count" : The number of times the batch size was executed on the
  model. A single model execution performs inferencing for the entire
  request batch and can perform inferencing for multiple requests if
  dynamic batching is enabled.

- “compute_input” : The count and cumulative duration to prepare input
  tensor data as required by the model framework / backend with the
  given batch size. For example, this duration should include the time
  to copy input tensor data to the GPU.

- “compute_infer” : The count and cumulative duration to execute the
  model with the given batch size.

- “compute_output” : The count and cumulative duration to extract
  output tensor data produced by the model framework / backend with
  the given batch size. For example, this duration should include the
  time to copy output tensor data from the GPU.

The `$duration_stat` object reports a count and a total time. This
format can be sampled to determine not only long-running averages but
also incremental averages between sample points.

```
$duration_stat =
{
  "count" : $number,
  "ns" : $number
}
```

- "count" : The number of times the statistic was collected.

- “ns” : The total duration for the statistic in nanoseconds.

```
$memory_usage =
{
  "type" : $string,
  "id" : $number,
  "byte_size" : $number
}
```

- "type" : The type of memory, the value can be "CPU", "CPU_PINNED", "GPU".

- "id" : The id of the memory, typically used with "type" to identify
  a device that hosts the memory.

- "byte_size" : The byte size of the memory.

### Statistics Response JSON Error Object

A failed statistics request will be indicated by an HTTP error status
(typically 400). The HTTP body must contain the
`$repository_statistics_error_response` object.

```
$repository_statistics_error_response =
{
  "error": $string
}
```

- “error” : The descriptive message for the error.

## GRPC

For the statistics extension Triton implements the following API:

```
service GRPCInferenceService
{
  …

  // Get the cumulative statistics for a model and version.
  rpc ModelStatistics(ModelStatisticsRequest)
          returns (ModelStatisticsResponse) {}
}
```

The ModelStatistics API returns model statistics. Errors are indicated
by the google.rpc.Status returned for the request. The OK code
indicates success and other codes indicate failure. The request and
response messages for ModelStatistics are:

```
message ModelStatisticsRequest
{
  // The name of the model. If not given returns statistics for all
  // models.
  string name = 1;

  // The version of the model. If not given returns statistics for
  // all model versions.
  string version = 2;
}

message ModelStatisticsResponse
{
  // Statistics for each requested model.
  repeated ModelStatistics model_stats = 1;
}
```

The statistics messages are:

```
// Statistic recording a cumulative duration metric.
message StatisticDuration
{
  // Cumulative number of times this metric occurred.
  uint64 count = 1;

  // Total collected duration of this metric in nanoseconds.
  uint64 ns = 2;
}

// Statistics for a specific model and version.
message ModelStatistics
{
  // The name of the model.
  string name = 1;

  // The version of the model.
  string version = 2;

  // The timestamp of the last inference request made for this model,
  // as milliseconds since the epoch.
  uint64 last_inference = 3;

  // The cumulative count of successful inference requests made for this
  // model. Each inference in a batched request is counted as an
  // individual inference. For example, if a client sends a single
  // inference request with batch size 64, "inference_count" will be
  // incremented by 64. Similarly, if a clients sends 64 individual
  // requests each with batch size 1, "inference_count" will be
  // incremented by 64. The "inference_count" value DOES NOT include cache hits.
  uint64 inference_count = 4;

  // The cumulative count of the number of successful inference executions
  // performed for the model. When dynamic batching is enabled, a single
  // model execution can perform inferencing for more than one inference
  // request. For example, if a clients sends 64 individual requests each
  // with batch size 1 and the dynamic batcher batches them into a single
  // large batch for model execution then "execution_count" will be
  // incremented by 1. If, on the other hand, the dynamic batcher is not
  // enabled for that each of the 64 individual requests is executed
  // independently, then "execution_count" will be incremented by 64.
  // The "execution_count" value DOES NOT include cache hits.
  uint64 execution_count = 5;

  // The aggregate statistics for the model.
  InferStatistics inference_stats = 6;

  // The aggregate statistics for each different batch size that is
  // executed in the model. The batch statistics indicate how many actual
  // model executions were performed and show differences due to different
  // batch size (for example, larger batches typically take longer to compute).
  repeated InferBatchStatistics batch_stats = 7;

  // The memory usage detected during model loading, which may be
  // used to estimate the memory to be released once the model is unloaded. Note
  // that the estimation is inferenced by the profiling tools and framework's
  // memory schema, therefore it is advised to perform experiments to understand
  // the scenario that the reported memory usage can be relied on. As a starting
  // point, the GPU memory usage for models in ONNX Runtime backend and TensorRT
  // backend is usually aligned.
  repeated MemoryUsage memory_usage = 8;

  // The key and value pairs for all decoupled responses statistics. The key is
  // a string identifying a set of response statistics aggregated together (i.e.
  // index of the response sent). The value is the aggregated response
  // statistics.
  map<string, InferResponseStatistics> response_stats = 9;
}

// Inference statistics.
message InferStatistics
{
  // Cumulative count and duration for successful inference
  // request. The "success" count and cumulative duration includes
  // cache hits.
  StatisticDuration success = 1;

  // Cumulative count and duration for failed inference
  // request.
  StatisticDuration fail = 2;

  // The count and cumulative duration that inference requests wait in
  // scheduling or other queues. The "queue" count and cumulative
  // duration includes cache hits.
  StatisticDuration queue = 3;

  // The count and cumulative duration to prepare input tensor data as
  // required by the model framework / backend. For example, this duration
  // should include the time to copy input tensor data to the GPU.
  // The "compute_input" count and cumulative duration do not account for
  // requests that were a cache hit. See the "cache_hit" field for more
  // info.
  StatisticDuration compute_input = 4;

  // The count and cumulative duration to execute the model.
  // The "compute_infer" count and cumulative duration do not account for
  // requests that were a cache hit. See the "cache_hit" field for more
  // info.
  StatisticDuration compute_infer = 5;

  // The count and cumulative duration to extract output tensor data
  // produced by the model framework / backend. For example, this duration
  // should include the time to copy output tensor data from the GPU.
  // The "compute_output" count and cumulative duration do not account for
  // requests that were a cache hit. See the "cache_hit" field for more
  // info.
  StatisticDuration compute_output = 6;

  // The count of response cache hits and cumulative duration to lookup
  // and extract output tensor data from the Response Cache on a cache
  // hit. For example, this duration should include the time to copy
  // output tensor data from the Response Cache to the response object.
  // On cache hits, triton does not need to go to the model/backend
  // for the output tensor data, so the "compute_input", "compute_infer",
  // and "compute_output" fields are not updated. Assuming the response
  // cache is enabled for a given model, a cache hit occurs for a
  // request to that model when the request metadata (model name,
  // model version, model inputs) hashes to an existing entry in the
  // cache. On a cache miss, the request hash and response output tensor
  // data is added to the cache. See response cache docs for more info:
  // https://github.com/triton-inference-server/server/blob/main/docs/response_cache.md
  StatisticDuration cache_hit = 7;

  // The count of response cache misses and cumulative duration to lookup
  // and insert output tensor data from the computed response to the cache
  // For example, this duration should include the time to copy
  // output tensor data from the response object to the Response Cache.
  // Assuming the response cache is enabled for a given model, a cache
  // miss occurs for a request to that model when the request metadata
  // does NOT hash to an existing entry in the cache. See the response
  // cache docs for more info:
  // https://github.com/triton-inference-server/server/blob/main/docs/response_cache.md
  StatisticDuration cache_miss = 8;
}

// Statistics per decoupled response.
message InferResponseStatistics
{
  // The count and cumulative duration to compute a response.
  StatisticDuration compute_infer = 1;

  // The count and cumulative duration to extract the output tensors of a
  // response.
  StatisticDuration compute_output = 2;

  // The count and cumulative duration for successful responses.
  StatisticDuration success = 3;

  // The count and cumulative duration for failed responses.
  StatisticDuration fail = 4;

  // The count and cumulative duration for empty responses.
  StatisticDuration empty_response = 5;
}

// Inference batch statistics.
message InferBatchStatistics
{
  // The size of the batch.
  uint64 batch_size = 1;

  // The count and cumulative duration to prepare input tensor data as
  // required by the model framework / backend with the given batch size.
  // For example, this duration should include the time to copy input
  // tensor data to the GPU.
  StatisticDuration compute_input = 2;

  // The count and cumulative duration to execute the model with the given
  // batch size.
  StatisticDuration compute_infer = 3;

  // The count and cumulative duration to extract output tensor data
  // produced by the model framework / backend with the given batch size.
  // For example, this duration should include the time to copy output
  // tensor data from the GPU.
  StatisticDuration compute_output = 4;
}

// Memory usage.
message MemoryUsage
{
  // The type of memory, the value can be "CPU", "CPU_PINNED", "GPU".
  string type = 1;

  // The id of the memory, typically used with "type" to identify
  // a device that hosts the memory.
  int64_t id = 2;

  // The byte size of the memory.
  uint64_t byte_size = 3;
}
```
