package org.langflow.sdk;

public final class AuthException extends LangflowException {
    public AuthException(int status, String message, String body) { super(status, message, body); }
}
