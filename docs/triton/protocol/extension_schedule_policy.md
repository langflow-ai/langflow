<!--
# Copyright 2020-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

# Schedule Policy Extension

This document describes Triton's schedule policy extension. The
schedule-policy extension allows an inference request to provide
parameters that influence how Triton handles and schedules the
request. Because this extension is supported, Triton reports
“schedule_policy” in the extensions field of its Server Metadata.
Note the policies are specific to [dynamic
batcher](https://github.com/triton-inference-server/server/blob/main/docs/user_guide/batcher.md#dynamic-batcher)
and only experimental support to [sequence
batcher](https://github.com/triton-inference-server/server/blob/main/docs/user_guide/batcher.md#sequence-batcher)
with the [direct](https://github.com/triton-inference-server/server/blob/main/docs/user_guide/architecture.md#direct)
scheduling strategy.

## Dynamic Batcher

The schedule-policy extension uses request parameters to indicate the
policy. The parameters and their type are:

- "priority" : int64 value indicating the priority of the
  request. Priority value zero indicates that the default priority
  level should be used (i.e. same behavior as not specifying the
  priority parameter). Lower value priorities indicate higher priority
  levels. Thus the highest priority level is indicated by setting the
  parameter to 1, the next highest is 2, etc.

- "timeout" : int64 value indicating the timeout value for the
  request, in microseconds. If the request cannot be completed within
  the time Triton will take a model-specific action such as
  terminating the request.

Both parameters are optional and, if not specified, Triton will handle
the request using the default priority and timeout values appropriate
for the model.

## Sequence Batcher with Direct Scheduling Strategy

**Note that the schedule policy for sequence batcher is at experimental stage
and it is subject to change.**

The schedule-policy extension uses request parameters to indicate the
policy. The parameters and their type are:

- "timeout" : int64 value indicating the timeout value for the
  request, in microseconds. If the request cannot be completed within
  the time Triton will terminate the request, as well as the corresponding
  sequence and received requests of the sequence. The timeout will only be
  applied to requests of the sequences that haven't been allocated a batch slot
  for execution, the requests of the sequences that have been allocated batch
  slots will not be affected by the timeout setting.

The parameter is optional and, if not specified, Triton will handle
the request and corresponding sequence based on the model configuration.