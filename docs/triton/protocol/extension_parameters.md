<!--
# Copyright 2023-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

# Parameters Extension

This document describes Triton's parameters extension. The
parameters extension allows an inference request to provide
custom parameters that cannot be provided as inputs. Because this extension is
supported, Triton reports “parameters” in the extensions field of its
Server Metadata. This extension uses the optional "parameters"
field in the KServe Protocol in
[HTTP](https://kserve.github.io/website/docs/concepts/architecture/data-plane/v2-protocol#inference-request-json-object)
and
[GRPC](https://kserve.github.io/website/docs/concepts/architecture/data-plane/v2-protocol#parameters).

The following parameters are reserved for Triton's usage and should not be
used as custom parameters:

- sequence_id
- sequence_start
- sequence_end
- priority
- timeout
- headers
- binary_data_output
- All the keys that start with `"triton_"` prefix. Some examples used today:
  - `"triton_enable_empty_final_response"` request parameter
  - `"triton_final_response"` response parameter

When using both GRPC and HTTP endpoints, you need to make sure to not use
the reserved parameters list to avoid unexpected behavior. The reserved
parameters are not accessible in the Triton C-API.

## HTTP/REST

The following example shows how a request can include custom parameters.

```
POST /v2/models/mymodel/infer HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Content-Length: <xx>
{
  "parameters" : { "my_custom_parameter" : 42 }
  "inputs" : [
    {
      "name" : "input0",
      "shape" : [ 2, 2 ],
      "datatype" : "UINT32",
      "data" : [ 1, 2, 3, 4 ]
    }
  ],
  "outputs" : [
    {
      "name" : "output0",
    }
  ]
}
```

## GRPC

The `parameters` field in the
ModelInferRequest message can be used to send custom parameters.

## Forwarding HTTP/GRPC Headers as Parameters

Triton can forward HTTP/GRPC headers as inference request parameters. By
specifying a regular expression in `--http-header-forward-pattern` and
`--grpc-header-forward-pattern`,
Triton will add the headers that match with the regular expression as request
parameters. All the forwarded headers will be added as a parameter with string
value. For example to forward all the headers that start with 'PREFIX_' from
both HTTP and GRPC, you should add `--http-header-forward-pattern PREFIX_.*
--grpc-header-forward-pattern PREFIX_.*` to your `tritonserver` command.

By default, the regular expression pattern matches headers with case-insensitive
mode according to the HTTP protocol. If you want to enforce case-sensitive mode,
simplying adding the `(?-i)` prefix which turns off case-insensitive mode, e.g.
`--http-header-forward-pattern (?-i)PREFIX_.*`. Note, headers sent through the
Python HTTP client may be automatically lower-cased by internal client libraries.

The forwarded headers can be accessed using the
[Python](https://github.com/triton-inference-server/python_backend#inference-request-parameters)
or C Backend APIs as inference request parameters.

