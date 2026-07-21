package org.langflow.sdk;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import okhttp3.HttpUrl;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

import java.io.IOException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.TimeUnit;

public final class HttpTransport {
    static final MediaType JSON = MediaType.get("application/json; charset=utf-8");
    public final ObjectMapper json = new ObjectMapper().registerModule(new JavaTimeModule());
    private final HttpUrl baseUrl;
    private final String apiKey;
    private final OkHttpClient client;

    public HttpTransport(String baseUrl, String apiKey, Duration connectTimeout, Duration readTimeout,
                         Duration writeTimeout, Duration callTimeout, OkHttpClient client) {
        this.baseUrl = HttpUrl.get(baseUrl.replaceAll("/+$", "") + "/");
        this.apiKey = apiKey;
        this.client = (client == null ? new OkHttpClient() : client).newBuilder()
                .addInterceptor(new DebugLoggingInterceptor())
                .connectTimeout(connectTimeout.toMillis(), TimeUnit.MILLISECONDS)
                .readTimeout(readTimeout.toMillis(), TimeUnit.MILLISECONDS)
                .writeTimeout(writeTimeout.toMillis(), TimeUnit.MILLISECONDS)
                .callTimeout(callTimeout.toMillis(), TimeUnit.MILLISECONDS)
                .build();
    }

    public OkHttpClient client() { return client; }

    public Request request(String method, String path, Object body, String accept) {
        try {
            RequestBody requestBody = body == null ? null : RequestBody.create(json.writeValueAsBytes(body), JSON);
            var builder = new Request.Builder().url(resolve(path)).header("Accept", accept);
            if (requestBody != null) builder.header("Content-Type", "application/json");
            if (apiKey != null && !apiKey.isBlank()) builder.header("x-api-key", apiKey);
            return builder.method(method, requestBody).build();
        } catch (Exception e) {
            throw new LangflowException("Unable to build Langflow request", e);
        }
    }

    public <T> T send(String method, String path, Object body, Class<T> type) {
        String response = execute(method, path, body);
        if (type == Void.class || response.isBlank()) return null;
        try { return json.readValue(response, type); }
        catch (Exception e) { throw new LangflowException("Invalid Langflow response", e); }
    }

    public <T> T send(String method, String path, Object body, TypeReference<T> type) {
        try { return json.readValue(execute(method, path, body), type); }
        catch (LangflowException e) { throw e; }
        catch (Exception e) { throw new LangflowException("Invalid Langflow response", e); }
    }

    private String execute(String method, String path, Object body) {
        try (Response response = client.newCall(request(method, path, body, "application/json")).execute()) {
            String text = response.body() == null ? "" : response.body().string();
            if (!response.isSuccessful()) throw httpError(response.code(), text);
            return text;
        } catch (LangflowException e) { throw e; }
        catch (IOException e) { throw new LangflowException("Could not connect to Langflow at " + baseUrl, e); }
    }

    private HttpUrl resolve(String path) {
        HttpUrl resolved = baseUrl.resolve(path.replaceFirst("^/", ""));
        if (resolved == null) throw new IllegalArgumentException("Invalid API path: " + path);
        return resolved;
    }

    public static String query(Map<String, ?> params) {
        var builder = new StringBuilder();
        params.forEach((key, value) -> {
            if (value == null) return;
            builder.append(builder.isEmpty() ? '?' : '&')
                    .append(URLEncoder.encode(key, StandardCharsets.UTF_8))
                    .append('=')
                    .append(URLEncoder.encode(value.toString(), StandardCharsets.UTF_8));
        });
        return builder.toString();
    }

    private LangflowException httpError(int status, String body) {
        String message = body;
        try {
            JsonNode detail = json.readTree(body).get("detail");
            if (detail != null) message = detail.isTextual() ? detail.asText() : detail.toString();
        } catch (Exception ignored) { }
        if (status == 401 || status == 403) return new AuthException(status, message, body);
        if (status == 404) return new NotFoundException(status, message, body);
        if (status == 400 || status == 422) return new ValidationException(status, message, body);
        return new LangflowException(status, message, body);
    }
}
