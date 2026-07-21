package org.langflow.sdk;

/** Base exception for transport, serialization, and HTTP API failures. */
public class LangflowException extends RuntimeException {
    private final int statusCode;
    private final String responseBody;

    public LangflowException(String message, Throwable cause) {
        super(message, cause);
        this.statusCode = 0;
        this.responseBody = null;
    }

    public LangflowException(int statusCode, String message, String responseBody) {
        super(message);
        this.statusCode = statusCode;
        this.responseBody = responseBody;
    }

    public int statusCode() { return statusCode; }
    public String responseBody() { return responseBody; }
}
