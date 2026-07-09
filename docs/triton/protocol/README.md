<!--
# Copyright 2020-2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

# HTTP/REST and GRPC Protocol

This directory contains documents related to the HTTP/REST and GRPC
protocols used by Triton. Triton uses the [KServe community standard
inference
protocols](https://github.com/kserve/kserve/tree/master/docs/predict-api/v2)
plus several extensions that are defined in the following documents:

- [Binary tensor data extension](./extension_binary_data.md)
- [Classification extension](./extension_classification.md)
- [Schedule policy extension](./extension_schedule_policy.md)
- [Sequence extension](./extension_sequence.md)
- [Shared-memory extension](./extension_shared_memory.md)
- [Model configuration extension](./extension_model_configuration.md)
- [Model repository extension](./extension_model_repository.md)
- [Statistics extension](./extension_statistics.md)
- [Trace extension](./extension_trace.md)
- [Logging extension](./extension_logging.md)
- [Parameters extension](./extension_parameters.md)

Note that some extensions introduce new fields onto the inference protocols,
and the other extensions define new protocols that Triton follows, please refer
to the extension documents for detail.

For the GRPC protocol, the [protobuf
specification](https://github.com/triton-inference-server/common/blob/main/protobuf/grpc_service.proto)
is also available. In addition, you can find the GRPC health checking protocol protobuf
specification [here](https://github.com/triton-inference-server/common/blob/main/protobuf/health.proto).

## Restricted Protocols

You can configure the Triton endpoints, which implement the protocols, to
restrict access to some protocols and to control network settings, please refer
to [protocol customization guide](https://github.com/triton-inference-server/server/blob/main/docs/customization_guide/inference_protocols.md#httprest-and-grpc-protocols) for detail.

## IPv6

Assuming your host or [docker config](https://docs.docker.com/config/daemon/ipv6/)
supports IPv6 connections, `tritonserver` can be configured to use IPv6
HTTP endpoints as follows:
```
$ tritonserver ... --http-address ipv6:[::1]&
...
I0215 21:04:11.572305 571 grpc_server.cc:4868] Started GRPCInferenceService at 0.0.0.0:8001
I0215 21:04:11.572528 571 http_server.cc:3477] Started HTTPService at ipv6:[::1]:8000
I0215 21:04:11.614167 571 http_server.cc:184] Started Metrics Service at ipv6:[::1]:8002
```

This can be confirmed via `netstat`, for example:
```
$ netstat -tulpn | grep tritonserver
tcp6      0      0 :::8000      :::*      LISTEN      571/tritonserver
tcp6      0      0 :::8001      :::*      LISTEN      571/tritonserver
tcp6      0      0 :::8002      :::*      LISTEN      571/tritonserver
```

And can be tested via `curl`, for example:
```
$ curl -6 --verbose "http://[::1]:8000/v2/health/ready"
*   Trying ::1:8000...
* TCP_NODELAY set
* Connected to ::1 (::1) port 8000 (#0)
> GET /v2/health/ready HTTP/1.1
> Host: [::1]:8000
> User-Agent: curl/7.68.0
> Accept: */*
>
* Mark bundle as not supporting multiuse
< HTTP/1.1 200 OK
< Content-Length: 0
< Content-Type: text/plain
<
* Connection #0 to host ::1 left intact
```


## Mapping Triton Server Error Codes to HTTP Status Codes

This table maps various Triton Server error codes to their corresponding HTTP status
codes. It can be used as a reference guide for understanding how Triton Server errors
are handled in HTTP responses.


| Triton Server Error Code                      | HTTP Status Code   | Description          |
| ----------------------------------------------| -------------------| ---------------------|
| `TRITONSERVER_ERROR_INTERNAL`                 | 500                | Internal Server Error|
| `TRITONSERVER_ERROR_NOT_FOUND`                | 404                | Not Found            |
| `TRITONSERVER_ERROR_UNAVAILABLE`              | 503                | Service Unavailable  |
| `TRITONSERVER_ERROR_UNSUPPORTED`              | 501                | Not Implemented      |
| `TRITONSERVER_ERROR_UNKNOWN`,<br>`TRITONSERVER_ERROR_INVALID_ARG`,<br>`TRITONSERVER_ERROR_ALREADY_EXISTS`,<br>`TRITONSERVER_ERROR_CANCELLED` | `400` | Bad Request (default for other errors)      |
