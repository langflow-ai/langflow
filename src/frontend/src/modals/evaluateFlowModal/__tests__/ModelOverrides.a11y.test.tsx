import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FlowModelPicker } from "@/controllers/API/queries/evals/types";
import { axe } from "@/utils/a11y-test";
import ModelOverrides from "../ModelOverrides";
import {
  type ChosenModels,
  MAX_MODEL_VARIANTS,
  type ModelVersion,
} from "../modelOverrideUtils";

// The real picker loads providers; the versions around it are what is under test.
jest.mock("../ModelOverrideRow", () => ({
  __esModule: true,
  default: ({
    version,
    picker,
  }: {
    version: number;
    picker: FlowModelPicker;
  }) => (
    <label>
      {picker.component}
      <input aria-label={`${picker.component} ${version}`} />
    </label>
  ),
}));

const GPT = [{ name: "gpt-4o", provider: "OpenAI" }];
const MINI = [{ name: "gpt-4o-mini", provider: "OpenAI" }];
const PICKERS: FlowModelPicker[] = [
  {
    node_id: "Agent-1",
    component: "Agent",
    field: "model",
    display_name: "Language Model",
    model_type: "language",
    value: GPT,
  },
];

function renderVersions(versions: ModelVersion[]) {
  const handlers = {
    onChange: jest.fn(),
    onDuplicate: jest.fn(),
    onRemove: jest.fn(),
  };
  const view = render(
    <ModelOverrides
      flowId="flow-1"
      pickers={PICKERS}
      versions={versions}
      {...handlers}
    />,
  );
  return { ...view, ...handlers };
}

const SWAPPED: ChosenModels = { "Agent-1::model": MINI };
const AS_SAVED: ChosenModels = {};
const versions = (count: number): ModelVersion[] =>
  Array.from({ length: count }, (_, key) => ({
    key,
    chosen: key === 1 ? SWAPPED : AS_SAVED,
  }));

describe("ModelOverrides versions", () => {
  it("should offer to compare from a single run", async () => {
    const { onDuplicate } = renderVersions(versions(1));
    await userEvent.click(screen.getByTestId("evaluate-models"));

    expect(screen.queryByTestId("model-version-0")).not.toBeInTheDocument();
    await userEvent.click(screen.getByTestId("model-version-add"));

    expect(onDuplicate).toHaveBeenCalledWith(0);
  });

  it("should show one card per version with what each changes", async () => {
    const { onDuplicate, onRemove } = renderVersions(versions(2));
    expect(screen.getByTestId("evaluate-models")).toHaveTextContent(
      "Comparing 2 versions",
    );
    await userEvent.click(screen.getByTestId("evaluate-models"));

    expect(screen.getByTestId("model-version-0")).toHaveTextContent(
      "As in the flow",
    );
    expect(screen.getByTestId("model-version-1")).toHaveTextContent(
      "1 changed",
    );
    await userEvent.click(screen.getByTestId("model-version-1-duplicate"));
    await userEvent.click(screen.getByTestId("model-version-0-remove"));

    expect(onDuplicate).toHaveBeenCalledWith(1);
    expect(onRemove).toHaveBeenCalledWith(0);
  });

  it("should stop adding versions at the limit", async () => {
    renderVersions(versions(MAX_MODEL_VARIANTS));
    await userEvent.click(screen.getByTestId("evaluate-models"));

    expect(screen.getByTestId("model-version-add")).toBeDisabled();
    expect(screen.getByTestId("model-version-0-duplicate")).toBeDisabled();
  });

  it("should have no accessibility violations while comparing", async () => {
    const { container } = renderVersions(versions(3));
    await userEvent.click(screen.getByTestId("evaluate-models"));

    expect(await axe(container)).toHaveNoViolations();
  });
});
