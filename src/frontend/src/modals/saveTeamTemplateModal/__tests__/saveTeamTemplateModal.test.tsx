import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import type { FlowType } from "@/types/flow";

const saveFlowMock = jest.fn(() => Promise.resolve());
const createTemplateMock = jest.fn(() =>
  Promise.resolve({ cleared_fields: 2 }),
);
const setSuccessDataMock = jest.fn();
const setErrorDataMock = jest.fn();

const currentFlow = {
  id: "flow-1",
  name: "Current workflow",
  description: "Current description",
  data: { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
  tags: ["existing"],
} as FlowType;

jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => saveFlowMock,
}));

jest.mock("@/controllers/API/queries/team-templates", () => ({
  usePostTeamTemplate: () => ({
    mutateAsync: createTemplateMock,
    isPending: false,
  }),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: { currentFlow: FlowType }) => unknown) =>
    selector({ currentFlow }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (
    selector: (state: {
      setSuccessData: typeof setSuccessDataMock;
      setErrorData: typeof setErrorDataMock;
    }) => unknown,
  ) =>
    selector({
      setSuccessData: setSuccessDataMock,
      setErrorData: setErrorDataMock,
    }),
}));

jest.mock("../../baseModal", () => {
  function BaseModal({
    children,
    open,
    onSubmit,
  }: {
    children: ReactNode;
    open: boolean;
    onSubmit: () => void;
  }) {
    if (!open) return null;
    return (
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        {children}
      </form>
    );
  }
  BaseModal.Header = ({ children }: { children: ReactNode }) => <>{children}</>;
  BaseModal.Content = ({ children }: { children: ReactNode }) => (
    <>{children}</>
  );
  BaseModal.Footer = ({
    submit,
  }: {
    submit: { label: string; dataTestId: string };
  }) => (
    <button type="submit" data-testid={submit.dataTestId}>
      {submit.label}
    </button>
  );
  return { __esModule: true, default: BaseModal };
});

import SaveTeamTemplateModal from "../index";

describe("SaveTeamTemplateModal", () => {
  beforeEach(() => jest.clearAllMocks());

  it("defaults to the current workflow values and submits user edits", async () => {
    const user = userEvent.setup();
    render(<SaveTeamTemplateModal open setOpen={jest.fn()} />);

    const nameInput = screen.getByLabelText("Template name");
    const descriptionInput = screen.getByLabelText("Description");
    expect(nameInput).toHaveValue("Current workflow");
    expect(descriptionInput).toHaveValue("Current description");

    await user.clear(nameInput);
    await user.type(nameInput, "Edited template");
    await user.clear(descriptionInput);
    await user.type(descriptionInput, "Edited description");
    await user.click(screen.getByTestId("save-team-template-submit"));

    await waitFor(() => expect(saveFlowMock).toHaveBeenCalled());
    expect(createTemplateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        source_flow_id: "flow-1",
        name: "Edited template",
        description: "Edited description",
      }),
    );
  });
});
