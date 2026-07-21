package org.langflow.example.web;

import org.langflow.sdk.v2.LangflowClient;
import org.langflow.sdk.v2.model.V2Models.WorkflowRequest;
import org.langflow.sdk.v2.model.V2Models.WorkflowResult;
import org.langflow.sdk.v2.model.V2Models.WorkflowStopResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/demo/v2")
public class V2Controller {
    private final LangflowClient client;
    public V2Controller(LangflowClient client) { this.client = client; }

    @PostMapping("/run")
    public WorkflowResult run(@RequestBody V2RunRequest body) {
        return client.execute(new WorkflowRequest(body.background(), false, body.flowId(),
                body.inputs(), body.globals()));
    }

    @GetMapping("/status")
    public WorkflowResult status(@RequestParam String jobId) { return client.status(jobId); }

    @PostMapping("/stop")
    public WorkflowStopResponse stop(@RequestBody StopRequest body) { return client.stop(body.jobId()); }

    public record V2RunRequest(String flowId, boolean background, Map<String, Object> inputs,
                               Map<String, String> globals) {}
    public record StopRequest(String jobId) {}
}
