package org.langflow.sdk.v1;

import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.langflow.sdk.v1.model.V1Models.RunRequest;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Flow;
import java.util.concurrent.TimeUnit;
import java.time.Duration;

import static org.junit.jupiter.api.Assertions.*;

class LangflowClientTest {
    MockWebServer server;
    LangflowClient client;

    @BeforeEach void setUp() throws Exception {
        server = new MockWebServer(); server.start();
        client = LangflowClient.builder(server.url("/").toString()).apiKey("secret").build();
    }
    @AfterEach void tearDown() throws Exception { client.close(); server.shutdown(); }

    @Test void runsV1FlowAndMapsText() throws Exception {
        server.enqueue(new MockResponse().setHeader("Content-Type", "application/json").setBody("""
                {"session_id":"s1","outputs":[{"outputs":[{"results":{"message":{"text":"hello"}}}]}]}
                """));
        assertEquals("hello", client.run("demo", "hi").firstTextOutput());
        var request = server.takeRequest();
        assertEquals("/api/v1/run/demo", request.getPath());
        assertEquals("secret", request.getHeader("x-api-key"));
    }

    @Test void streamsV1WithOkHttpSse() throws Exception {
        server.enqueue(new MockResponse().setHeader("Content-Type", "text/event-stream").setBody(
                "data: {\"event\":\"token\",\"data\":{\"chunk\":\"Hi\"}}\n\n"));
        CountDownLatch done = new CountDownLatch(1);
        StringBuilder text = new StringBuilder();
        client.stream("demo", new RunRequest("hi")).subscribe(new Flow.Subscriber<>() {
            public void onSubscribe(Flow.Subscription s) { s.request(Long.MAX_VALUE); }
            public void onNext(org.langflow.sdk.v1.model.V1Models.StreamChunk item) { text.append(item.text()); }
            public void onError(Throwable t) { done.countDown(); }
            public void onComplete() { done.countDown(); }
        });
        assertTrue(done.await(3, TimeUnit.SECONDS));
        assertEquals("Hi", text.toString());
    }

    @Test void parameterizesHostPortApiKeyAndTimeouts() throws Exception {
        try (var configured = LangflowClient.builder(server.getHostName(), server.getPort())
                .scheme("http").apiKey("configured-key")
                .connectTimeout(Duration.ofSeconds(2)).readTimeout(Duration.ofSeconds(3))
                .writeTimeout(Duration.ofSeconds(4)).callTimeout(Duration.ofSeconds(5)).build()) {
            server.enqueue(new MockResponse().setHeader("Content-Type", "application/json").setBody("[]"));
            assertTrue(configured.listFlows().isEmpty());
            var request = server.takeRequest();
            assertEquals(server.getPort(), request.getRequestUrl().port());
            assertEquals("configured-key", request.getHeader("x-api-key"));
        }
    }
}
