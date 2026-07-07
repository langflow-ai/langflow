<!--
# Copyright (c) 2020, NVIDIA CORPORATION. All rights reserved.
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

# Classification Extension

This document describes Triton's classification extension.  The
classification extension allows Triton to return an output as a
classification index and (optional) label instead of returning the
output as raw tensor data.  Because this extension is supported,
Triton reports “classification” in the extensions field of its Server
Metadata.

An inference request can use the “classification” parameter to request
that one or more classifications be returned for an output. For such
an output the returned tensor will not be the shape and type produced
by the model, but will instead be type BYTES with shape [ batch-size,
\<count\> ] where each element returns the classification index and
label as a single string. The \<count\> dimension of the returned tensor
will equal the “count” value specified in the classification
parameter.

When the classification parameter is used, Triton will determine the
top-n classifications as the n highest-valued elements in the output
tensor compared using the output tensor’s data type. For example, if
an output tensor is [ 1, 5, 10, 4 ], the highest-valued element is 10
(index 2), followed by 5 (index 1), followed by 4 (index 3), followed
by 1 (index 0). So, for example, the top-2 classifications by index
are [ 2, 1 ].

The format of the returned string will be “\<value\>:\<index\>[:\<label\>]”,
where \<index\> is the index of the class in the model output tensor,
\<value\> is the value associated with that index in the model output,
and the \<label\> associated with that index is optional. For example,
continuing the example from above, the returned tensor will be [
“10:2”, “5:1” ]. If the model has labels associated with those
indices, the returned tensor will be [ “10:2:apple”, “5:1:pickle” ].

## HTTP/REST

In all JSON schemas shown in this document `$number`, `$string`, `$boolean`,
`$object` and `$array` refer to the fundamental JSON types. #optional
indicates an optional JSON field.

The classification extension requires that the “classification”
parameter, when applied to a requested inference output, be recognized
by Triton as follows:

- “classification” : `$number` indicating the number of classes that
  should be returned for the output.

The following example shows how the classification parameter is used
in an inference request.

```
POST /v2/models/mymodel/infer HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Content-Length: <xx>
{
  "id" : "42",
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
      "parameters" : { "classification" : 2 }
    }
  ]
}
```

For the above request Triton will return the “output0” output tensor
as a STRING tensor with shape [ 2 ]. Assuming the model produces
output0 tensor [ 1.1, 3.3, 0.5, 2.4 ] from the above inputs, the
response will be the following.

```
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: <yy>
{
  "id" : "42"
  "outputs" : [
    {
      "name" : "output0",
      "shape" : [ 2 ],
      "datatype"  : "STRING",
      "data" : [ "3.3:1", "2.4:3" ]
    }
  ]
}
```

If the model has labels associated with each classification index
Triton will return those as well, as shown below.

```
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: <yy>
{
  "id" : "42"
  "outputs" : [
    {
      "name" : "output0",
      "shape" : [ 2 ],
      "datatype"  : "STRING",
      "data" : [ "3.3:1:index_1_label", "2.4:3:index_3_label" ]
    }
  ]
}
```

## GRPC

The classification extension requires that the “classification”
parameter, when applied to a requested inference output, be recognized
by Triton as follows:

- “classification” : int64_param indicating the number of classes that
  should be returned for the output.

The following example shows how the classification parameter is used
in an inference request.

```
ModelInferRequest {
  model_name : "mymodel"
  model_version : -1
  inputs [
    {
      name : "input0"
      shape : [ 2, 2 ]
      datatype : "UINT32"
      contents { int_contents : [ 1, 2, 3, 4 ] }
    }
  ]
  outputs [
    {
      name : "output0"
      parameters [
        {
          key : "classification"
          value : { int64_param : 2 }
        }
      ]
    }
  ]
}
```

For the above request Triton will return the “output0” output tensor
as a STRING tensor with shape [ 2 ]. Assuming the model produces
output0 tensor [ 1.1, 3.3, 0.5, 2.4 ] from the above inputs, the
response will be the following.

```
ModelInferResponse {
  model_name : "mymodel"
  outputs [
    {
      name : "output0"
      shape : [ 2 ]
      datatype  : "STRING"
      contents { bytes_contents : [ "3.3:1", "2.4:3" ] }
    }
  ]
}
```
