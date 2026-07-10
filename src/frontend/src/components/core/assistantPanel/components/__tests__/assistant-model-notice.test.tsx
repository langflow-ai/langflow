/**
 * The (i) indicator that surfaces a silent model failure the turn recovered
 * from (fallback / remediation). Renders only when notices are present.
 */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import type { AssistantModelNotice as NoticeType } from "@/controllers/API/queries/agentic";
import { AssistantModelNotice } from "../assistant-model-notice";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, unknown>) =>
      opts ? `${key}:${JSON.stringify(opts)}` : key,
  }),
  initReactI18next: { type: "3rdParty", init: jest.fn() },
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({
    content,
    children,
  }: {
    content: React.ReactNode;
    children: React.ReactNode;
  }) => (
    <div>
      {children}
      <div data-testid="tooltip-content">{content}</div>
    </div>
  ),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <span data-icon={name} />,
}));

describe("AssistantModelNotice", () => {
  it("renders nothing when there are no notices", () => {
    const { container } = render(<AssistantModelNotice notices={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the (i) indicator when a fallback notice is present", () => {
    const notices: NoticeType[] = [
      {
        type: "model_fallback",
        reason: "requires a subscription",
        failed_model: "glm-5:cloud",
        used_model: "llama3.2:latest",
      },
    ];
    render(<AssistantModelNotice notices={notices} />);
    expect(screen.getByTestId("assistant-model-notice")).toBeInTheDocument();
  });

  it("describes a fallback with failed and used models", () => {
    const notices: NoticeType[] = [
      {
        type: "model_fallback",
        reason: "requires a subscription",
        failed_model: "glm-5:cloud",
        used_model: "llama3.2:latest",
      },
    ];
    render(<AssistantModelNotice notices={notices} />);
    const content = screen.getByTestId("tooltip-content").textContent ?? "";
    expect(content).toContain("assistant.modelNotice.fallback");
    expect(content).toContain("glm-5:cloud");
    expect(content).toContain("llama3.2:latest");
  });

  it("uses the remediation string when the model was retried, not swapped", () => {
    const notices: NoticeType[] = [
      { type: "model_remediation", reason: "tools unsupported", failed_model: "gpt-5.6" },
    ];
    render(<AssistantModelNotice notices={notices} />);
    const content = screen.getByTestId("tooltip-content").textContent ?? "";
    expect(content).toContain("assistant.modelNotice.remediation");
  });
});
