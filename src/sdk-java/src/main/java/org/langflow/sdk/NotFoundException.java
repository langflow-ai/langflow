package org.langflow.sdk;

public final class NotFoundException extends LangflowException {
    public NotFoundException(int status, String message, String body) { super(status, message, body); }
}
