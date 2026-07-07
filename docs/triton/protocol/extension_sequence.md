<!--
# Copyright (c) 2020-2023, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

# Sequence Extension

This document describes Triton's sequence extension. The sequence
extension allows Triton to support stateful models that expect a
sequence of related inference requests.

An inference request can specify that it is part of a sequence using
the “sequence_id” parameter in the request and by using the
“sequence_start” and “sequence_end” parameters to indicate the start
and end of sequences.

Because this extension is supported, Triton reports "sequence"
in the extensions field of its Server Metadata. Triton may additionally
report "sequence(string_id)" in the extensions field of the Server Metadata
if the "sequence_id" parameter supports string types.

- "sequence_id" : a string or uint64 value that identifies the sequence to which
  a request belongs. All inference requests that belong to the same sequence
  must use the same sequence ID. A sequence ID of 0 or "" indicates the
  inference request is not part of a sequence.

- "sequence_start" : boolean value if set to true in a request
  indicates that the request is the first in a sequence. If not set,
  or set to false the request is not the first in a sequence. If set
  the "sequence_id" parameter must be set to a non-zero or non-empty string
  value.

- "sequence_end" : boolean value if set to true in a request indicates
  that the request is the last in a sequence. If not set, or set to
  false the request is not the last in a sequence. If set the
  "sequence_id" parameter must be set to a non-zero or non-empty string
  value.

## HTTP/REST

The following example shows how a request is marked as part of a
sequence. In this case the sequence_start and sequence_end parameters
are not used which means that this request is neither the start nor
end of the sequence.

```
POST /v2/models/mymodel/infer HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Content-Length: <xx>
{
  "parameters" : { "sequence_id" : 42 }
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

The example below uses a v4 UUID string as the value for the "sequence_id"
parameter.

```
POST /v2/models/mymodel/infer HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Content-Length: <xx>
{
  "parameters" : { "sequence_id" : "e333c95a-07fc-42d2-ab16-033b1a566ed5" }
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

In addition to supporting the sequence parameters described above, the
GRPC API adds a streaming version of the inference API to allow a
sequence of inference requests to be sent over the same GRPC
stream. This streaming API is not required to be used for requests
that specify a sequence_id and may be used by requests that do not
specify a sequence_id. The ModelInferRequest is the same as for the
ModelInfer API.  The ModelStreamInferResponse message is shown below.

```
service GRPCInferenceService
{
  …

  // Perform inference using a specific model with GRPC streaming.
  rpc ModelStreamInfer(stream ModelInferRequest) returns (stream ModelStreamInferResponse) {}
}

// Response message for ModelStreamInfer.
message ModelStreamInferResponse
{
  // The message describing the error. The empty message
  // indicates the inference was successful without errors.
  String error_message = 1;

  // Holds the results of the request.
  ModelInferResponse infer_response = 2;
}
```
