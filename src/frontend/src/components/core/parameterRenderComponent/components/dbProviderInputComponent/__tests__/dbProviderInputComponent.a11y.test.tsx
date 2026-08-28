import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { axe } from "@/utils/a11y-test";
import DBProviderInputComponent, { DBProviderInput } from "..";

type MockGlobalVariablesQuery = {
  data: never[];
  isSuccess: boolean;
  isFetching: boolean;
  isError: boolean;
  fetchStatus: "idle" | "fetching" | "paused";
};

let mockGlobalVariablesQuery: MockGlobalVariablesQuery = {
  data: [],
  isSuccess: true,
  isFetching: false,
  isError: false,
  fetchStatus: "idle",
};
let mockGlobalVariablesQueryState = {
  status: "success",
  fetchStatus: "idle",
  isInvalidated: false,
};
const mockGetQueryState = jest.fn(() => mockGlobalVariablesQueryState);
const mockQueryClient = { getQueryState: mockGetQueryState };
const mockUseGetGlobalVariables = jest.fn(
  (_options?: unknown) => mockGlobalVariablesQuery,
);

jest.mock("@tanstack/react-query", () => ({
  ...jest.requireActual("@tanstack/react-query"),
  useQueryClient: () => mockQueryClient,
}));
let mockCurrentFlowId = "flow-project-a";

jest.mock("@/controllers/API/queries/variables", () => ({
  getGlobalVariablesQueryKey: ({ flowId }: { flowId?: string } = {}) => [
    "useGetGlobalVariables",
    flowId,
    undefined,
  ],
  useGetGlobalVariables: (options?: unknown) =>
    mockUseGetGlobalVariables(options),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: { currentFlowId: string }) => unknown) =>
    selector({ currentFlowId: mockCurrentFlowId }),
}));

const baseProps = {
  id: "db-provider-field",
  value: "chroma" as const,
  globalVariables: [],
  disabled: false,
  onValueChange: jest.fn(),
};

const fieldProps = {
  id: "dbprovider_backend",
  value: "chroma" as const,
  disabled: false,
  editNode: false,
  handleOnNewValue: jest.fn(),
};

describe("DBProviderInput", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <MemoryRouter>
        <span id="field-label">Vector store provider</span>
        <DBProviderInput {...baseProps} ariaLabelledBy="field-label" />
      </MemoryRouter>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: aria-labelledby (field label) must win over the
  // literal aria-label prop, and must not be composed with the selected
  // provider's name (role="combobox" screen-reader double-announce lesson
  // from dropdownComponent/modelInputComponent/connectionComponent).
  it("uses the field's real label as the trigger's accessible name", () => {
    render(
      <MemoryRouter>
        <span id="field-label">Vector store provider</span>
        <DBProviderInput
          {...baseProps}
          ariaLabelledBy="field-label"
          aria-label="Should be overridden"
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("combobox", { name: "Vector store provider" }),
    ).toBeInTheDocument();
  });

  it("falls back to the literal aria-label when ariaLabelledBy is absent", () => {
    render(
      <MemoryRouter>
        <DBProviderInput {...baseProps} aria-label="Database provider" />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("combobox", { name: "Database provider" }),
    ).toBeInTheDocument();
  });

  it("should_not_emit_a_dead_aria_label_alongside_the_field_label", () => {
    render(
      <MemoryRouter>
        <span id="field-label">Vector store provider</span>
        <DBProviderInput
          {...baseProps}
          ariaLabelledBy="field-label"
          aria-label="Database provider"
        />
      </MemoryRouter>,
    );

    // aria-labelledby already wins; leaving aria-label on the element too
    // would strand a name no assistive tech ever reads.
    expect(
      screen.getByRole("combobox", { name: "Vector store provider" }),
    ).not.toHaveAttribute("aria-label");
  });
});

describe("DBProviderInputComponent", () => {
  beforeEach(() => {
    mockCurrentFlowId = "flow-project-a";
    mockGlobalVariablesQuery = {
      data: [],
      isSuccess: true,
      isFetching: false,
      isError: false,
      fetchStatus: "idle",
    };
    mockGlobalVariablesQueryState = {
      status: "success",
      fetchStatus: "idle",
      isInvalidated: false,
    };
    mockGetQueryState.mockClear();
    mockUseGetGlobalVariables.mockClear();
  });

  // The canvas field label reaches the trigger only if the wrapper forwards
  // ariaLabelledBy out of baseInputProps — testing DBProviderInput alone
  // cannot catch that link being dropped.
  it("should_name_the_trigger_from_the_forwarded_field_label", () => {
    render(
      <MemoryRouter>
        <span id="db-label">Knowledge Base</span>
        <DBProviderInputComponent {...fieldProps} ariaLabelledBy="db-label" />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("combobox", { name: "Knowledge Base" }),
    ).toBeInTheDocument();
    expect(mockUseGetGlobalVariables).toHaveBeenCalledWith({
      flowId: "flow-project-a",
      enabled: true,
    });
  });

  it("waits for a flow before initializing a default", async () => {
    mockCurrentFlowId = "";
    const handleOnNewValue = jest.fn();
    const { rerender } = render(
      <MemoryRouter>
        <DBProviderInputComponent
          {...fieldProps}
          value={undefined}
          handleOnNewValue={handleOnNewValue}
        />
      </MemoryRouter>,
    );

    expect(handleOnNewValue).not.toHaveBeenCalled();

    mockCurrentFlowId = "flow-project-a";
    rerender(
      <MemoryRouter>
        <DBProviderInputComponent
          {...fieldProps}
          value={undefined}
          handleOnNewValue={handleOnNewValue}
        />
      </MemoryRouter>,
    );

    await waitFor(() => expect(handleOnNewValue).toHaveBeenCalledTimes(1));
  });

  it("waits for a successful scoped variable query before initializing a default", async () => {
    const handleOnNewValue = jest.fn();
    mockGlobalVariablesQuery = {
      data: [],
      isSuccess: false,
      isFetching: true,
      isError: false,
      fetchStatus: "fetching",
    };
    const { rerender } = render(
      <MemoryRouter>
        <DBProviderInputComponent
          {...fieldProps}
          value={undefined}
          handleOnNewValue={handleOnNewValue}
        />
      </MemoryRouter>,
    );

    expect(handleOnNewValue).not.toHaveBeenCalled();

    mockGlobalVariablesQuery = {
      data: [],
      isSuccess: true,
      isFetching: false,
      isError: false,
      fetchStatus: "idle",
    };
    rerender(
      <MemoryRouter>
        <DBProviderInputComponent
          {...fieldProps}
          value={undefined}
          handleOnNewValue={handleOnNewValue}
        />
      </MemoryRouter>,
    );

    await waitFor(() => expect(handleOnNewValue).toHaveBeenCalledTimes(1));
  });

  it("waits for paused and invalidated scoped queries before initializing", async () => {
    const handleOnNewValue = jest.fn();
    mockGlobalVariablesQuery = {
      data: [],
      isSuccess: true,
      isFetching: false,
      isError: false,
      fetchStatus: "paused",
    };
    const { rerender } = render(
      <MemoryRouter>
        <DBProviderInputComponent
          {...fieldProps}
          value={undefined}
          handleOnNewValue={handleOnNewValue}
        />
      </MemoryRouter>,
    );

    expect(handleOnNewValue).not.toHaveBeenCalled();

    mockGlobalVariablesQuery = {
      data: [],
      isSuccess: true,
      isFetching: false,
      isError: false,
      fetchStatus: "idle",
    };
    mockGlobalVariablesQueryState = {
      status: "success",
      fetchStatus: "idle",
      isInvalidated: true,
    };
    rerender(
      <MemoryRouter>
        <DBProviderInputComponent
          {...fieldProps}
          value={undefined}
          handleOnNewValue={handleOnNewValue}
        />
      </MemoryRouter>,
    );

    expect(handleOnNewValue).not.toHaveBeenCalled();
    expect(mockGetQueryState).toHaveBeenCalledWith([
      "useGetGlobalVariables",
      "flow-project-a",
      undefined,
    ]);

    mockGlobalVariablesQueryState = {
      status: "success",
      fetchStatus: "idle",
      isInvalidated: false,
    };
    mockGlobalVariablesQuery = {
      ...mockGlobalVariablesQuery,
      data: [],
    };
    rerender(
      <MemoryRouter>
        <DBProviderInputComponent
          {...fieldProps}
          value={undefined}
          handleOnNewValue={handleOnNewValue}
        />
      </MemoryRouter>,
    );

    await waitFor(() => expect(handleOnNewValue).toHaveBeenCalledTimes(1));
  });
});
