<!--
# Copyright (c) 2022, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

# Trace Extension

This document describes Triton's trace extension. The trace extension enables
the client to configure the trace settings during a Triton run. Because this
extension is supported, Triton reports “trace” in the extensions field of
its Server Metadata.

## HTTP/REST

In all JSON schemas shown in this document `$number`, `$string`, `$boolean`,
`$object` and `$array` refer to the fundamental JSON types. `#optional`
indicates an optional JSON field.

Triton exposes the trace endpoint at the following URL. The client may use
HTTP GET request to retrieve the current trace setting. A HTTP POST request
will modify the trace setting, and the endpoint will return the updated trace
setting on success or an error in the case of failure. Optional model name
can be provided to get or to set the trace settings for specific model.

```
GET v2[/models/${MODEL_NAME}]/trace/setting

POST v2[/models/${MODEL_NAME}]/trace/setting
```

### Trace Setting Response JSON Object

A successful trace setting request is indicated by a 200 HTTP status
code. The response object, identified as `$trace_setting_response`, is
returned in the HTTP body for every successful trace setting request.

```
$trace_setting_response =
{
  $trace_setting, ...
}

$trace_setting = $string : $string | [ $string, ...]
```

Each `$trace_setting` JSON describes a “name”/”value” pair, where the “name” is
the name of the trace setting and the “value” is a `$string representation` of the
setting value, or an array of `$string` for some settings. Currently the following
trace settings are defined:

- "trace_file" : the file where the trace output will be saved. If
"log_frequency" is set, this will be the prefix of the files to save the
trace output, resulting files in name `"${trace_file}.0", "${trace_file}.1", ...`,
see trace setting "log_frequency" below for detail.
- "trace_level" : the trace level. "OFF" to disable tracing,
"TIMESTAMPS" to trace timestamps, "TENSORS" to trace tensors.
This value is an array of string where user may specify multiple levels to
trace multiple information.
- "trace_rate" : the trace sampling rate. The value represents how many requests
will one trace be sampled from. For example, if the trace rate is "1000",
1 trace will be sampled for every 1000 requests.
- "trace_count" : the number of remaining traces to be sampled. Once the value
becomes "0", no more traces will be sampled for the trace setting, and the
collected traces will be written to indexed trace file in the format described
in "log_frequency", regardless of the "log_frequency" status.
If the value is "-1", the number of traces to be sampled will not be limited.
- "log_frequency" : the frequency that Triton will log the
trace output to the files. If the value is "0", Triton will only log
the trace output to `${trace_file}` when shutting down. Otherwise, Triton will log
the trace output to `${trace_file}.${idx}` when it collects
the specified number of traces. For example, if the log frequency is "100",
when Triton collects the 100-th trace, it logs the traces to file
`"${trace_file}.0"`, and when it collects the 200-th trace, it logs the 101-th to
the 200-th traces to file `"${trace_file}.1"`. Note that the file index will be
reset to 0 when "trace_file" setting is updated.


### Trace Setting Response JSON Error Object

A failed trace setting request will be indicated by an HTTP error status
(typically 400). The HTTP body must contain the
`$trace_setting_error_response` object.

```
$trace_setting_error_response =
{
  "error": $string
}
```

- “error” : The descriptive message for the error.

#### Trace Setting Request JSON Object

A trace setting request is made with a HTTP POST to
the trace endpoint. In the corresponding response the HTTP body contains the
response JSON. A successful request is indicated by a 200 HTTP status code.

The request object, identified as `$trace_setting_request` must be provided in the HTTP
body.

```
$trace_setting_request =
{
  $trace_setting, ...
}
```

The `$trace_setting` JSON is defined in
[Trace Setting Response JSON Object](#trace-setting-response-json-object), only the specified
settings will be updated. In addition to the values mentioned in response JSON
object, JSON null value may be used to remove the specification of
the trace setting. In such case, the current global setting will be used.
Similarly, if this is the first request to initialize a model trace settings,
for the trace settings that are not specified in the request, the current global
setting will be used.

## GRPC

For the trace extension Triton implements the following API:

```
service GRPCInferenceService
{
  …

  // Update and get the trace setting of the Triton server.
  rpc TraceSetting(TraceSettingRequest)
          returns (TraceSettingResponse) {}
}
```

The Trace Setting API returns the latest trace settings. Errors are indicated
by the google.rpc.Status returned for the request. The OK code
indicates success and other codes indicate failure. The request and
response messages for Trace Setting are:

```
message TraceSettingRequest
{
  // The values to be associated with a trace setting.
  // If no value is provided, the setting will be clear and
  // the global setting value will be used.
  message SettingValue
  {
    repeated string value = 1;
  }

  // The new setting values to be updated,
  // settings that are not specified will remain unchanged.
  map<string, SettingValue> settings = 1;

  // The name of the model to apply the new trace settings.
  // If not given, the new settings will be applied globally.
  string model_name = 2;
}

message TraceSettingResponse
{
  message SettingValue
  {
    repeated string value = 1;
  }

  // The latest trace settings.
  map<string, SettingValue> settings = 1;
}
```

The trace settings are mentioned in
[Trace Setting Response JSON Object](#trace-setting-response-json-object).
Note that if this is the first request to initialize
a model trace settings, for the trace settings that are not specified
in the request, the value will be copied from the current global settings.
