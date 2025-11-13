import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  jest,
} from "@jest/globals";
import { cleanup, render } from "@testing-library/react";
import React from "react";
import { LangflowChat } from "../LangflowChat";
import type { LangflowChatProps } from "../types";

describe("LangflowChat", () => {
  const requiredProps: LangflowChatProps = {
    hostUrl: "https://example.com",
    flowId: "flow-123",
    apiKey: "chat-widget-test-id", // pragma: allowlist secret
  };

  beforeEach(() => {
    cleanup();
    document.body.innerHTML = "";
  });

  afterEach(() => {
    cleanup();
    jest.restoreAllMocks();
  });

  it("renders the underlying web component with the expected attributes", () => {
    const { container } = render(<LangflowChat {...requiredProps} />);

    const webComponent = container.querySelector("langflow-chat");
    expect(webComponent).not.toBeNull();
    expect(webComponent?.getAttribute("host_url")).toBe(requiredProps.hostUrl);
    expect(webComponent?.getAttribute("flow_id")).toBe(requiredProps.flowId);
    expect(webComponent?.getAttribute("api_key")).toBe(requiredProps.apiKey);
  });
});
