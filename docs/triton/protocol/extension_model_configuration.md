<!--
# Copyright (c) 2020-2023, NVIDIA CORPORATION. All rights reserved.
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

# Model Configuration Extension

This document describes Triton's model configuration extension.  The
model configuration extension allows Triton to return server-specific
information.  Because this extension is supported, Triton reports
“model_configuration” in the extensions field of its Server Metadata.

## HTTP/REST

In all JSON schemas shown in this document `$number`, `$string`, `$boolean`,
`$object` and `$array` refer to the fundamental JSON types. #optional
indicates an optional JSON field.

Triton exposes the model configuration endpoint at the following
URL. The versions portion of the URL is optional; if not provided
Triton will return model configuration for the highest-numbered
version of the model.

```
GET v2/models/${MODEL_NAME}[/versions/${MODEL_VERSION}]/config
```

A model configuration request is made with an HTTP GET to the model
configuration endpoint.A successful model configuration request is
indicated by a 200 HTTP status code. The model configuration response
object, identified as `$model_configuration_response`, is returned in
the HTTP body for every successful request.

```
$model_configuration_response =
{
  # configuration JSON
}
```

The contents of the response will be the JSON representation of the
model's configuration described by the [ModelConfig message from
model_config.proto](https://github.com/triton-inference-server/common/blob/main/protobuf/model_config.proto).

A failed model configuration request must be indicated by an HTTP
error status (typically 400). The HTTP body must contain the
`$model_configuration_error_response` object.

```
$model_configuration_error_response =
{
  "error": <error message string>
}
```

- “error” : The descriptive message for the error.

## GRPC

The GRPC definition of the service is:

```
service GRPCInferenceService
{
  …

  // Get model configuration.
  rpc ModelConfig(ModelConfigRequest) returns (ModelConfigResponse) {}
}
```

Errors are indicated by the google.rpc.Status returned for the
request. The OK code indicates success and other codes indicate
failure. The request and response messages for ModelConfig are:

```
message ModelConfigRequest
{
  // The name of the model.
  string name = 1;

  // The version of the model. If not given the version of the model
  // is selected automatically based on the version policy.
  string version = 2;
}

message ModelConfigResponse
{
  // The model configuration.
  ModelConfig config = 1;
}
```

Where the ModelConfig message is defined in
[model_config.proto](https://github.com/triton-inference-server/common/blob/main/protobuf/model_config.proto).
