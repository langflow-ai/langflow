package org.langflow.sdk.v2;

import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.langflow.sdk.v2.model.V2Models.WorkflowJob;
import org.langflow.sdk.v2.model.V2Models.WorkflowRequest;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class LangflowClientTest {
    MockWebServer server;
    LangflowClient client;
    @BeforeEach void setUp() throws Exception {
        server = new MockWebServer(); server.start();
        client = LangflowClient.builder(server.url("/").toString()).apiKey("secret").build();
    }
    @AfterEach void tearDown() throws Exception { client.close(); server.shutdown(); }

    @Test void executesBackgroundWorkflow() throws Exception {
        server.enqueue(new MockResponse().setHeader("Content-Type", "application/json").setBody("""
                {"object":"job","job_id":"9ef96787-c34f-4e63-81c5-1979f2142b2f","flow_id":"demo","status":"queued"}
                """));
        var result = client.execute(WorkflowRequest.background("demo", Map.of("ChatInput-1.input_value", "hi")));
        assertInstanceOf(WorkflowJob.class, result);
        assertEquals("/api/v2/workflows", server.takeRequest().getPath());
    }

    @Test void rejectsConflictingModesLocally() {
        assertThrows(IllegalArgumentException.class, () -> new WorkflowRequest(true, true, "demo", Map.of(), Map.of()));
    }
}
