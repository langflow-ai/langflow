import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "@/utils/a11y-test";
import JevJudgeToggle, { isJevModel, JEV_MODEL } from "../JevJudgeToggle";

const providers = {
  current: [] as { provider: string; is_configured: boolean }[],
};

jest.mock("@/controllers/API/queries/models/use-get-model-providers", () => ({
  useGetModelProviders: () => ({ data: providers.current, isSuccess: true }),
}));
jest.mock("@/modals/modelProviderModal", () => ({
  __esModule: true,
  default: () => <div data-testid="provider-modal" />,
}));

describe("JevJudgeToggle", () => {
  it("should report the toggle and recognize the Jev model", async () => {
    const onChange = jest.fn();
    render(<JevJudgeToggle flowId="f" checked={false} onChange={onChange} />);
    await userEvent.click(screen.getByTestId("judge-use-jev"));
    expect(onChange).toHaveBeenCalledWith(true);
    expect(isJevModel(JEV_MODEL)).toBe(true);
    expect(isJevModel({ name: "gpt", provider: "OpenAI", icon: "" })).toBe(
      false,
    );
  });

  it("should offer to add a key when TypeSafe is not configured", async () => {
    providers.current = [{ provider: "TypeSafe", is_configured: false }];
    render(<JevJudgeToggle flowId="f" checked onChange={jest.fn()} />);
    expect(screen.getByTestId("judge-jev-missing-key")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByTestId("provider-modal")).toBeInTheDocument();
  });

  it("should not warn once the key is configured", () => {
    providers.current = [{ provider: "TypeSafe", is_configured: true }];
    render(<JevJudgeToggle flowId="f" checked onChange={jest.fn()} />);
    expect(screen.queryByTestId("judge-jev-missing-key")).toBeNull();
  });

  it("should have no accessibility violations", async () => {
    providers.current = [{ provider: "TypeSafe", is_configured: false }];
    const { container } = render(
      <JevJudgeToggle flowId="f" checked onChange={jest.fn()} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
