package org.langflow.example.web;

import jakarta.annotation.Resource;
import org.langflow.sdk.v1.LangflowClient;
import org.langflow.sdk.v1.model.V1Models.Flow;
import org.langflow.sdk.v1.model.V1Models.RunRequest;
import org.langflow.sdk.v1.model.V1Models.RunResponse;
import org.langflow.sdk.v1.model.V1Models.StreamChunk;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Flow.Subscriber;
import java.util.concurrent.Flow.Subscription;

@RestController
@RequestMapping("/demo/v1")
public class V1Controller {
    @Resource
    private LangflowClient langflowV1Client;
    public V1Controller(LangflowClient client) { this.langflowV1Client = client; }

    @GetMapping("/flows")
    public List<Flow> flows() { return langflowV1Client.listFlows(); }

    @PostMapping("/run")
    public RunResponse run(@RequestBody V1RunRequest body) {
        return langflowV1Client.runFlow(body.flowId(), new RunRequest(body.inputValue(), body.inputType(),
                body.outputType(), body.tweaks(), false));
    }

    @GetMapping(path = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter stream(@RequestParam String flowId, @RequestParam String inputValue) {
        SseEmitter emitter = new SseEmitter(0L);
        langflowV1Client.stream(flowId, new RunRequest(inputValue)).subscribe(new Subscriber<>() {
            private Subscription subscription;
            @Override
            public void onSubscribe(Subscription value) { subscription = value; value.request(1); }
            @Override
            public void onNext(StreamChunk chunk) {
                try {
                    emitter.send(SseEmitter.event().name(chunk.event()).data(chunk));
                    subscription.request(1);
                } catch (IOException error) { subscription.cancel(); emitter.completeWithError(error); }
            }
            @Override
            public void onError(Throwable error) { emitter.completeWithError(error); }
            @Override
            public void onComplete() { emitter.complete(); }
        });
        return emitter;
    }

    public record V1RunRequest(String flowId, String inputValue, String inputType, String outputType,
                               Map<String, Object> tweaks) {
        public V1RunRequest {
            inputType = inputType == null ? "chat" : inputType;
            outputType = outputType == null ? "chat" : outputType;
        }
    }
}
