import { extractApiErrorMessage } from "../extract-api-error-message";

describe("extractApiErrorMessage", () => {
  const FALLBACK = "Default error";

  it("should_return_string_detail_when_detail_is_string", () => {
    // Arrange — simple string detail (e.g. HTTPException)
    const error = {
      response: { data: { detail: "Server not found" } },
    };

    // Act
    const result = extractApiErrorMessage(error, FALLBACK);

    // Assert
    expect(result).toBe("Server not found");
  });

  it("should_return_joined_msg_fields_when_detail_is_array_of_validation_errors", () => {
    // Arrange — FastAPI RequestValidationError format (the exact bug scenario)
    const error = {
      response: {
        data: {
          detail: [
            {
              type: "value_error",
              loc: ["body", "args"],
              msg: "Value error, Argument '-y' is not allowed for security reasons",
              input: ["-y", "@antv/mcp-server-chart"],
              ctx: {
                error: "Argument '-y' is not allowed for security reasons",
              },
            },
          ],
        },
      },
    };

    // Act
    const result = extractApiErrorMessage(error, FALLBACK);

    // Assert — must be the readable msg, NOT "[object Object]"
    expect(result).toBe(
      "Value error, Argument '-y' is not allowed for security reasons",
    );
    expect(result).not.toContain("[object Object]");
  });

  it("should_join_multiple_validation_errors_with_semicolon", () => {
    // Arrange — multiple validation errors in one response
    const error = {
      response: {
        data: {
          detail: [
            { msg: "Field 'name' is required" },
            { msg: "Field 'command' is required" },
          ],
        },
      },
    };

    // Act
    const result = extractApiErrorMessage(error, FALLBACK);

    // Assert
    expect(result).toBe(
      "Field 'name' is required; Field 'command' is required",
    );
  });

  it("should_stringify_array_items_without_msg_field", () => {
    // Arrange — array items that don't have a msg field
    const error = {
      response: {
        data: {
          detail: [{ error: "something went wrong" }],
        },
      },
    };

    // Act
    const result = extractApiErrorMessage(error, FALLBACK);

    // Assert — should use String() coercion, not crash
    expect(result).toBe("[object Object]");
  });

  it("should_extract_msg_from_single_object_detail", () => {
    // Arrange — detail is a single object with msg
    const error = {
      response: { data: { detail: { msg: "Invalid configuration" } } },
    };

    // Act
    const result = extractApiErrorMessage(error, FALLBACK);

    // Assert
    expect(result).toBe("Invalid configuration");
  });

  it("should_extract_message_from_single_object_detail", () => {
    // Arrange — detail is a single object with message (not msg)
    const error = {
      response: {
        data: { detail: { message: "Connection refused" } },
      },
    };

    // Act
    const result = extractApiErrorMessage(error, FALLBACK);

    // Assert
    expect(result).toBe("Connection refused");
  });

  it("should_json_stringify_object_without_msg_or_message", () => {
    // Arrange — object detail without known keys
    const error = {
      response: { data: { detail: { code: 500, info: "crash" } } },
    };

    // Act
    const result = extractApiErrorMessage(error, FALLBACK);

    // Assert
    expect(result).toBe('{"code":500,"info":"crash"}');
  });

  it("should_use_error_message_when_no_detail", () => {
    // Arrange — no response.data.detail, just error.message
    const error = { message: "Network Error" };

    // Act
    const result = extractApiErrorMessage(error, FALLBACK);

    // Assert
    expect(result).toBe("Network Error");
  });

  it("should_use_fallback_when_no_detail_and_no_message", () => {
    // Arrange — completely empty error
    const error = {};

    // Act
    const result = extractApiErrorMessage(error, FALLBACK);

    // Assert
    expect(result).toBe(FALLBACK);
  });
});
