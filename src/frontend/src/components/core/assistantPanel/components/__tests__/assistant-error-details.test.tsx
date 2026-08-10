/**
 * The "Error details" expander renders only when the SSE error event carried
 * the additive ``detail`` object, starts collapsed, and shows each optional
 * field through i18n keys.
 */

import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import type { AgenticErrorDetail } from "@/controllers/API/queries/agentic";
import { AssistantErrorDetails } from "../assistant-error-details";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
  initReactI18next: { type: "3rdParty", init: jest.fn() },
}));

function makeDetail(
  overrides: Partial<AgenticErrorDetail> = {},
): AgenticErrorDetail {
  return {
    step: "generating_flow",
    component_id: "OpenAIModel-x1",
    tool: "web_search",
    raw_cause: "Error building Component OpenAIModel-x1: Error code: 401",
    recommendation: "Check the API key in Settings → Model Providers.",
    ...overrides,
  };
}

describe("AssistantErrorDetails", () => {
  it("should render a collapsed details element with the i18n title", () => {
    render(<AssistantErrorDetails detail={makeDetail()} />);

    const details = screen.getByTestId("assistant-error-details");
    expect(details).toBeInTheDocument();
    expect(details).not.toHaveAttribute("open");
    expect(
      screen.getByText("assistant.errorDetails.title"),
    ).toBeInTheDocument();
  });

  it("should show every provided field after expanding", () => {
    render(<AssistantErrorDetails detail={makeDetail()} />);

    fireEvent.click(screen.getByText("assistant.errorDetails.title"));

    expect(screen.getByText("generating_flow")).toBeInTheDocument();
    expect(screen.getByText("OpenAIModel-x1")).toBeInTheDocument();
    expect(screen.getByText("web_search")).toBeInTheDocument();
    expect(
      screen.getByText("Check the API key in Settings → Model Providers."),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("assistant-error-details-raw-cause"),
    ).toHaveTextContent("Error building Component OpenAIModel-x1");
  });

  it("should omit rows for absent fields", () => {
    render(
      <AssistantErrorDetails
        detail={makeDetail({
          component_id: undefined,
          tool: undefined,
          recommendation: undefined,
        })}
      />,
    );

    expect(
      screen.queryByText("assistant.errorDetails.component"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("assistant.errorDetails.tool"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("assistant.errorDetails.recommendation"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("assistant.errorDetails.step:"),
    ).toBeInTheDocument();
  });

  it("should render nothing for an empty detail object", () => {
    const { container } = render(<AssistantErrorDetails detail={{}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
