<!--
# Copyright 2020-2022, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

# Model Repository Extension

This document describes Triton's model repository extension.  The
model-repository extension allows a client to query and control the
one or more model repositories being served by Triton.  Because this
extension is supported, Triton reports “model_repository” in the
extensions field of the Server Metadata. This extension has an
optional component, described below, that allows the unload API to
specify the "unload_dependents" parameter. Versions of Triton that
support this optional component will also report
"model_repository(unload_dependents)" in the extensions field of the
Server Metadata.

## HTTP/REST

In all JSON schemas shown in this document `$number`, `$string`, `$boolean`,
`$object` and `$array` refer to the fundamental JSON types. `#optional`
indicates an optional JSON field.

The model-repository extension requires Index, Load and Unload
APIs. Triton exposes the endpoints at the following URLs.

```
POST v2/repository/index

POST v2/repository/models/${MODEL_NAME}/load

POST v2/repository/models/${MODEL_NAME}/unload
```

### Index

The index API returns information about every model available in a
model repository, even if it is not currently loaded into Triton. The
index API provides a way to determine which models can potentially be
loaded by the Load API. A model-repository index request is made with
an HTTP POST to the index endpoint. In the corresponding response the
HTTP body contains the JSON response.

The index request object, identified as `$repository_index_request`, is
required in the HTTP body of the POST request.

```
$repository_index_request =
{
  "ready" : $boolean #optional,
}
```

- "ready" : Optional, default is false. If true return only models ready for inferencing.

A successful index request is indicated by a 200 HTTP status code. The
response object, identified as `$repository_index_response`, is returned
in the HTTP body for every successful request.

```
$repository_index_response =
[
  {
    "name" : $string,
    "version" : $string #optional,
    "state" : $string,
    "reason" : $string
  },
  …
]
```

- “name” : The name of the model.
- “version” : The version of the model.
- “state” : The state of the model.
- “reason” : The reason, if any, that the model is in the current state.

A failed index request must be indicated by an HTTP error status
(typically 400). The HTTP body must contain the
`$repository_index_error_response` object.

```
$repository_index_error_response =
{
  "error": $string
}
```

- “error” : The descriptive message for the error.

### Load

The load API requests that a model be loaded into Triton, or reloaded
if the model is already loaded. A load request is made with an HTTP
POST to a load endpoint. The HTTP body may be empty or may contain
the load request object, identified as `$repository_load_request`.
A successful load request is indicated by a 200 HTTP status.


```
$repository_load_request =
{
  "parameters" : $parameters #optional
}
```

- "parameters" : An object containing zero or more parameters for this
  request expressed as key/value pairs. See
  [Parameters](https://github.com/kserve/kserve/blob/master/docs/predict-api/v2/required_api.md#parameters)
  for more information.

The load API accepts the following parameters:

- "config" : string parameter that contains a JSON representation of the model
configuration, which must be able to be parsed into [ModelConfig message from
model_config.proto](https://github.com/triton-inference-server/common/blob/main/protobuf/model_config.proto).
This config will be used for loading the model instead of the one in
the model directory. If config is provided, the (re-)load will be triggered as
the model metadata has been updated, and the same (re-)load behavior will be
applied.

- "file:\<version\>/\<file-name\>" : The serialized model file, base64 encoded.
This convention will be used to specify the override model directory to load
the model from. For instance, if the user wants to specify a model directory
that contains an ONNX model as version 2, then the user will specify the
parameter to "file:2/model.onnx" : "\<base64-encoded-file-content\>". Note that
"config" parameter must be provided to serve as the model configuration of the
override model directory.

A failed load request must be indicated by an HTTP error status
(typically 400). The HTTP body must contain the
`$repository_load_error_response` object.

```
$repository_load_error_response =
{
  "error": $string
}
```
- “error” : The descriptive message for the error.

#### Examples

For the following request, Triton will load the model "mymodel" with provided
model configuration and model file.

```
POST /v2/repository/models/mymodel/load HTTP/1.1
Host: localhost:8000
{
  "parameters": {
    "config": "{
      "name": "mymodel",
      "backend": "onnxruntime",
      "inputs": [{
          "name": "INPUT0",
          "datatype": "FP32",
          "shape": [ 1 ]
        }
      ],
      "outputs": [{
          "name": "OUTPUT0",
          "datatype": "FP32",
          "shape": [ 1 ]
        }
      ]
    }",

    "file:1/model.onnx" : "<base64-encoded-file-content>"
  }
}
```

### Unload

The unload API requests that a model be unloaded from Triton. An
unload request is made with an HTTP POST to an unload endpoint. The
HTTP body may be empty or may contain the unload request object,
identified as `$repository_unload_request`. A successful unload request
is indicated by a 200 HTTP status.

```
$repository_unload_request =
{
  "parameters" : $parameters #optional
}
```

- "parameters" : An object containing zero or more parameters for this
  request expressed as key/value pairs. See
  [Parameters](https://github.com/kserve/kserve/blob/master/docs/predict-api/v2/required_api.md#parameters)
  for more information.

The unload API accepts the following parameters:

- "unload_dependents" : boolean parameter indicating that in addition
  to unloading the requested model, also unload any dependent model
  that was loaded along with the requested model. For example, request to
  unload the models composing an ensemble will unload the ensemble as well.

A failed unload request must be indicated by an HTTP error status
(typically 400). The HTTP body must contain the
`$repository_unload_error_response` object.

```
$repository_unload_error_response =
{
  "error": $string
}
```

- “error” : The descriptive message for the error.

## GRPC

The model-repository extension requires the following API:

```
service GRPCInferenceService
{
  …

  // Get the index of model repository contents.
  rpc RepositoryIndex(RepositoryIndexRequest)
          returns (RepositoryIndexResponse) {}

  // Load or reload a model from a repository.
  rpc RepositoryModelLoad(RepositoryModeLoadRequest)
          returns (RepositoryModelLoadResponse) {}

  // Unload a model.
  rpc RepositoryModelUnload(RepositoryModelUnloadRequest)
          returns (RepositoryModelUnloadResponse) {}
}

message ModelRepositoryParameter
{
  // The parameter value can be a string, an int64, a boolean
  // or a message specific to a predefined parameter.
  oneof parameter_choice
  {
    // A boolean parameter value.
    bool bool_param = 1;

    // An int64 parameter value.
    int64 int64_param = 2;

    // A string parameter value.
    string string_param = 3;

    // A bytes parameter value.
    bytes bytes_param = 4;
  }
}
```

### Index

The RepositoryIndex API returns information about every model
available in a model repository, even if it is not currently loaded
into Triton. Errors are indicated by the google.rpc.Status returned
for the request. The OK code indicates success and other codes
indicate failure. The request and response messages for
RepositoryIndex are:

```
message RepositoryIndexRequest
{
  // The name of the repository. If empty the index is returned
  // for all repositories.
  string repository_name = 1;

  // If true return only models currently ready for inferencing.
  bool ready = 2;
}

message RepositoryIndexResponse
{
  // Index entry for a model.
  message ModelIndex {
    // The name of the model.
    string name = 1;

    // The version of the model.
    string version = 2;

    // The state of the model.
    string state = 3;

    // The reason, if any, that the model is in the given state.
    string reason = 4;
  }

  // An index entry for each model.
  repeated ModelIndex models = 1;
}
```

### Load

The RepositoryModelLoad API requests that a model be loaded into
Triton, or reloaded if the model is already loaded. Errors are
indicated by the google.rpc.Status returned for the request. The OK
code indicates success and other codes indicate failure. The request
and response messages for RepositoryModelLoad are:

```
message RepositoryModelLoadRequest
{
  // The name of the repository to load from. If empty the model
  // is loaded from any repository.
  string repository_name = 1;

  // The name of the model to load, or reload.
  string model_name = 2;

  // Optional parameters.
  map<string, ModelRepositoryParameter> parameters = 3;
}

message RepositoryModelLoadResponse
{
}
```

The RepositoryModelLoad API accepts the following parameters:

- "config" : string parameter that contains a JSON representation of the model
configuration, which must be able to be parsed into [ModelConfig message from
model_config.proto](https://github.com/triton-inference-server/common/blob/main/protobuf/model_config.proto).
This config will be used for loading the model instead of the one in
the model directory. If config is provided, the (re-)load will be triggered as
the model metadata has been updated, and the same (re-)load behavior will be
applied.

- "file:\<version\>/\<file-name\>" : bytes parameter that contains the model
file content. This convention will be used to specify the override model
directory to load the model from. For instance, if the user wants to specify a
model directory that contains an ONNX model as version 2, then the user will
specify the parameter to "file:2/model.onnx" : "\<file-content\>". Note that
"config" parameter must be provided to serve as the model configuration of the
override model directory.

### Unload

The RepositoryModelUnload API requests that a model be unloaded from
Triton. Errors are indicated by the google.rpc.Status returned for the
request. The OK code indicates success and other codes indicate
failure. The request and response messages for RepositoryModelUnload
are:

```
message RepositoryModelUnloadRequest
{
  // The name of the repository from which the model was originally
  // loaded. If empty the repository is not considered.
  string repository_name = 1;

  // The name of the model to unload.
  string model_name = 2;

  // Optional parameters.
  map<string, ModelRepositoryParameter> parameters = 3;
}

message RepositoryModelUnloadResponse
{
}
```

The RepositoryModelUnload API accepts the following parameters:

- "unload_dependents" : boolean parameter indicating that in addition
  to unloading the requested model, also unload any dependent model
  that was loaded along with the requested model. For example, request to
  unload the models composing an ensemble will unload the ensemble as well.