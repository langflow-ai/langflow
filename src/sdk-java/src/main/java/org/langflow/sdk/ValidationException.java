package org.langflow.sdk;

public final class ValidationException extends LangflowException {
    public ValidationException(int status, String message, String body) { super(status, message, body); }
}
