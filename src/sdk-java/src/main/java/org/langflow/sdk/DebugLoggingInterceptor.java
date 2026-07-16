package org.langflow.sdk;

import okhttp3.Interceptor;
import okhttp3.MediaType;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.ResponseBody;
import okio.Buffer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/** Logs Langflow request and response parameters without consuming response bodies. */
public final class DebugLoggingInterceptor implements Interceptor {
    private static final Logger LOG = LoggerFactory.getLogger("org.langflow.sdk.http");
    private static final long MAX_LOG_BODY_BYTES = 1024L * 1024L;
    private static final String REDACTED = "***";

    @Override
    public Response intercept(Chain chain) throws IOException {
        if (!LOG.isDebugEnabled()) return chain.proceed(chain.request());

        Request request = chain.request();
        String requestId = UUID.randomUUID().toString();
        String requestBody = readRequestBody(request);
        LOG.debug("Langflow request started: requestId={}, method={}, url={}, headers={}, body={}",
                requestId, request.method(), request.url(), redactedHeaders(request), redactJsonSecrets(requestBody));

        long started = System.nanoTime();
        try {
            Response response = chain.proceed(request);
            long elapsedMs = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started);
            String contentType = response.header("Content-Type", "");
            if (contentType.toLowerCase(Locale.ROOT).contains("text/event-stream")) {
                LOG.debug("Langflow response received: requestId={}, status={}, elapsedMs={}, contentType={}, body=<SSE stream>",
                        requestId, response.code(), elapsedMs, contentType);
            } else {
                ResponseBody preview = response.peekBody(MAX_LOG_BODY_BYTES);
                String body = preview.string();
                boolean truncated = response.body() != null && response.body().contentLength() > MAX_LOG_BODY_BYTES;
                LOG.debug("Langflow response received: requestId={}, status={}, elapsedMs={}, body={}{}",
                        requestId, response.code(), elapsedMs, redactJsonSecrets(body), truncated ? " <truncated>" : "");
            }
            return response;
        } catch (IOException | RuntimeException error) {
            long elapsedMs = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started);
            LOG.debug("Langflow request failed: requestId={}, elapsedMs={}, error={}",
                    requestId, elapsedMs, error.toString());
            throw error;
        }
    }

    private static String readRequestBody(Request request) {
        if (request.body() == null) return "";
        try {
            Buffer buffer = new Buffer();
            request.body().writeTo(buffer);
            Charset charset = StandardCharsets.UTF_8;
            MediaType type = request.body().contentType();
            if (type != null) charset = type.charset(StandardCharsets.UTF_8);
            long byteCount = Math.min(buffer.size(), MAX_LOG_BODY_BYTES);
            String value = buffer.readString(byteCount, charset);
            return buffer.exhausted() ? value : value + " <truncated>";
        } catch (Exception error) {
            return "<unavailable: " + error.getClass().getSimpleName() + ">";
        }
    }

    private static String redactedHeaders(Request request) {
        var copy = request.headers().newBuilder();
        copy.set("x-api-key", REDACTED);
        copy.set("Authorization", REDACTED);
        return copy.build().toString().replace('\n', ' ').trim();
    }

    /** Best-effort masking for common secret fields while retaining other request parameters. */
    private static String redactJsonSecrets(String value) {
        if (value == null || value.isEmpty()) return value;
        return value.replaceAll(
                "(?i)(\\\"(?:api[_-]?key|authorization|password|secret|token)\\\"\\s*:\\s*\\\")[^\\\"]*(\\\")",
                "$1" + REDACTED + "$2"
        );
    }
}
