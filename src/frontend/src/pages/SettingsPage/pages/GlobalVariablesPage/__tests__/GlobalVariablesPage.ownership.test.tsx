import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import type { ReactNode } from "react";
import type { GlobalVariable } from "@/types/global_variables";
import GlobalVariablesPage from "../index";

let mockVariables: GlobalVariable[] = [];
let mockUseLabelSeam = false;
const mockListFilter = jest.fn();

const variable = (
  id: string,
  isOwner: boolean | undefined,
  name = id.toUpperCase(),
): GlobalVariable => ({
  id,
  name,
  value: "value",
  type: "Generic",
  default_fields: [],
  is_owner: isOwner,
});

jest.mock("@/contexts/permissionsContext", () => ({
  PermissionsProvider: ({ children }: { children: ReactNode }) => children,
  usePermissions: () => ({
    can: () => true,
    isLoading: false,
    isError: false,
    permissions: {},
  }),
}));
const mockDeleteVariable = jest.fn();
const mockSetErrorData = jest.fn();
jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: () => ({ data: mockVariables }),
  useDeleteGlobalVariables: () => ({ mutate: mockDeleteVariable }),
}));
jest.mock("@/components/core/dropdownComponent", () => ({
  __esModule: true,
  default: ({ children }: { children?: ReactNode }) => children ?? null,
}));
jest.mock("@/components/core/GlobalVariableModal/GlobalVariableModal", () => ({
  __esModule: true,
  default: ({
    children,
    open,
    setOpen,
    initialData,
  }: {
    children?: ReactNode;
    open?: boolean;
    setOpen?: (open: boolean) => void;
    initialData?: GlobalVariable;
  }) =>
    initialData ? (
      open ? (
        <div role="dialog" aria-label={`Edit ${initialData.name}`}>
          <button type="button" onClick={() => setOpen?.(false)}>
            Close editor
          </button>
        </div>
      ) : null
    ) : (
      (children ?? null)
    ),
}));
jest.mock("@/customization/components/custom-variable-share-action", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
  ForwardedIconComponent: () => null,
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({ setErrorData: mockSetErrorData }),
}));
jest.mock("@/customization/hooks/use-custom-resource-list-filter", () => ({
  useCustomResourceListFilter: (...args: unknown[]) => mockListFilter(...args),
}));
jest.mock("@/customization/components/custom-resource-access-label", () => ({
  __esModule: true,
  default: (props: {
    resourceType: string;
    resourceId: string;
    isOwned: boolean;
    fallback?: ReactNode;
  }) =>
    mockUseLabelSeam ? (
      <span
        data-testid="access-label"
        data-resource-type={props.resourceType}
        data-resource-id={props.resourceId}
        data-owned={String(props.isOwned)}
        data-has-fallback={String(props.fallback != null)}
      />
    ) : (
      jest
        .requireActual(
          "@/customization/components/custom-resource-access-label",
        )
        .default(props)
    ),
}));

const actualListFilter = jest.requireActual(
  "@/customization/hooks/use-custom-resource-list-filter",
).useCustomResourceListFilter;

const ownedOnly = <T,>(
  _type: string,
  items: T[],
  isOwned: (item: T) => boolean,
) => ({
  items: items.filter(isOwned),
  tools: <button type="button">Owned</button>,
});

const cellsIn = (colId: string) =>
  Array.from(
    document.querySelectorAll<HTMLElement>(
      `.ag-center-cols-container [role="gridcell"][col-id="${colId}"]`,
    ),
  );

const nameCells = () =>
  Array.from(
    document.querySelectorAll<HTMLElement>(
      '.ag-center-cols-container [role="gridcell"][col-id="name"]',
    ),
  );

// AG Grid dispatches row clicks, key events and column sizing asynchronously;
// wait them out before asserting that something did NOT happen.
const settle = () =>
  act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 100));
  });

describe("GlobalVariablesPage ownership seams", () => {
  beforeEach(() => {
    mockUseLabelSeam = false;
    mockListFilter.mockReset();
    mockListFilter.mockImplementation(actualListFilter);
    // Give the real grid a viewport in jsdom so it renders rows.
    jest
      .spyOn(HTMLElement.prototype, "clientWidth", "get")
      .mockReturnValue(1000);
    jest
      .spyOn(HTMLElement.prototype, "clientHeight", "get")
      .mockReturnValue(600);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("should_render_every_variable_name_as_plain_text_when_the_seams_are_the_default", async () => {
    mockVariables = [variable("a", true), variable("b", false)];
    render(<GlobalVariablesPage />);
    await screen.findByText("A");

    expect(nameCells().map((cell) => cell.textContent?.trim())).toEqual([
      "A",
      "B",
    ]);
    expect(screen.queryByTestId("access-label")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Owned" }),
    ).not.toBeInTheDocument();
  });

  it("should_give_the_seam_valid_variables_and_an_is_owner_rule", async () => {
    mockVariables = [
      variable("mine", true),
      variable("shared", false),
      variable("legacy", undefined),
    ];
    render(<GlobalVariablesPage />);
    await screen.findByText("MINE");

    const [type, items, isOwned] = mockListFilter.mock.calls.at(-1);
    expect(type).toBe("variable");
    expect(items.map(isOwned)).toEqual([true, false, true]);
  });

  it("should_render_only_filtered_variables_and_the_tools_in_the_header", async () => {
    mockVariables = [variable("mine", true), variable("shared", false)];
    mockListFilter.mockImplementation(ownedOnly);
    render(<GlobalVariablesPage />);
    await screen.findByText("MINE");

    expect(nameCells().map((cell) => cell.textContent?.trim())).toEqual([
      "MINE",
    ]);
    const tools = screen.getByRole("button", { name: "Owned" });
    expect(tools.parentElement).toBe(
      screen.getByTestId("api-key-button-store").parentElement,
    );
  });

  it("should_keep_the_header_tools_and_show_no_rows_when_every_variable_is_shared", async () => {
    mockVariables = [variable("x", false), variable("y", false)];
    mockListFilter.mockImplementation(ownedOnly);
    render(<GlobalVariablesPage />);
    await screen.findByRole("button", { name: "Owned" });

    expect(nameCells()).toHaveLength(0);
    expect(mockListFilter.mock.calls.at(-1)?.[1]).toHaveLength(2);
  });

  it("should_show_the_shared_pill_only_for_non_owned_rows_when_the_label_is_the_default", async () => {
    mockVariables = [
      variable("mine", true),
      variable("shared", false),
      variable("legacy", undefined),
    ];
    render(<GlobalVariablesPage />);
    await screen.findByText("MINE");

    expect(cellsIn("access").map((cell) => cell.textContent?.trim())).toEqual([
      "",
      "Shared",
      "",
    ]);
    expect(screen.getAllByText("Shared")).toHaveLength(1);
  });

  it("should_render_the_label_in_the_access_cell_not_the_name_cell", async () => {
    mockUseLabelSeam = true;
    mockVariables = [variable("mine", true), variable("shared", false)];
    render(<GlobalVariablesPage />);
    await screen.findByText("MINE");

    for (const cell of nameCells()) {
      expect(within(cell).queryByTestId("access-label")).toBeNull();
    }
    const [mineCell, sharedCell] = cellsIn("access");
    const sharedLabel = within(sharedCell).getByTestId("access-label");
    expect(sharedLabel).toHaveAttribute("data-resource-type", "variable");
    expect(sharedLabel).toHaveAttribute("data-resource-id", "shared");
    expect(sharedLabel).toHaveAttribute("data-owned", "false");
    expect(sharedLabel).toHaveAttribute("data-has-fallback", "true");
    const mineLabel = within(mineCell).getByTestId("access-label");
    expect(mineLabel).toHaveAttribute("data-owned", "true");
    expect(mineLabel).toHaveAttribute("data-has-fallback", "false");
  });

  it("should_render_one_label_per_row_when_there_are_many_variables", async () => {
    mockUseLabelSeam = true;
    mockVariables = Array.from({ length: 22 }, (_, index) =>
      variable(`v${String(index).padStart(2, "0")}`, index % 2 === 0),
    );
    render(<GlobalVariablesPage />);
    await screen.findByText("V00");

    const cells = cellsIn("access");
    expect(cells.length).toBeGreaterThan(0);
    for (const cell of cells) {
      expect(within(cell).getAllByTestId("access-label")).toHaveLength(1);
    }
  });

  describe("rows the seam leaves visible", () => {
    const cellOf = (name: string) =>
      nameCells().find(
        (cell) => cell.textContent?.trim() === name,
      ) as HTMLElement;

    beforeEach(() => {
      mockDeleteVariable.mockReset();
      mockSetErrorData.mockReset();
    });

    it("should_hide_an_invalid_provider_key_and_say_why_when_it_failed_validation", async () => {
      mockVariables = [
        variable("mine", true),
        {
          ...variable("openai", true, "OPENAI_API_KEY"),
          type: "Credential",
          is_valid: false,
          validation_error: "Invalid key",
        },
      ];
      render(<GlobalVariablesPage />);
      await screen.findByText("MINE");

      expect(nameCells().map((cell) => cell.textContent?.trim())).toEqual([
        "MINE",
      ]);
      expect(mockSetErrorData).toHaveBeenCalledWith(
        expect.objectContaining({
          list: expect.arrayContaining(["OPENAI_API_KEY: Invalid key"]),
        }),
      );
      expect(mockListFilter.mock.calls.at(-1)?.[1]).toHaveLength(1);
    });

    it("should_open_the_editor_when_an_owned_row_is_clicked", async () => {
      mockVariables = [variable("mine", true), variable("shared", false)];
      render(<GlobalVariablesPage />);
      await screen.findByText("MINE");

      fireEvent.click(cellOf("MINE"));

      expect(
        await screen.findByRole("dialog", { name: "Edit MINE" }),
      ).toBeInTheDocument();
    });

    it("should_not_open_the_editor_for_a_shared_row_without_a_permission_entry", async () => {
      mockVariables = [variable("mine", true), variable("shared", false)];
      render(<GlobalVariablesPage />);
      await screen.findByText("SHARED");

      fireEvent.click(cellOf("SHARED"));
      await settle();

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      // Positive control: the same gesture on an owned row does open it.
      fireEvent.click(cellOf("MINE"));
      expect(
        await screen.findByRole("dialog", { name: "Edit MINE" }),
      ).toBeInTheDocument();
    });

    it("should_not_open_the_editor_when_enter_is_pressed_on_a_shared_row", async () => {
      mockVariables = [variable("mine", true), variable("shared", false)];
      render(<GlobalVariablesPage />);
      await screen.findByText("SHARED");

      fireEvent.keyDown(cellOf("SHARED"), { key: "Enter" });
      await settle();

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      fireEvent.keyDown(cellOf("MINE"), { key: "Enter" });
      expect(
        await screen.findByRole("dialog", { name: "Edit MINE" }),
      ).toBeInTheDocument();
    });

    it("should_open_the_editor_when_enter_is_pressed_on_an_owned_row", async () => {
      mockVariables = [variable("mine", true)];
      render(<GlobalVariablesPage />);
      await screen.findByText("MINE");

      fireEvent.keyDown(cellOf("MINE"), { key: "Enter" });

      expect(
        await screen.findByRole("dialog", { name: "Edit MINE" }),
      ).toBeInTheDocument();
    });

    it("should_return_focus_to_the_row_cell_when_the_editor_closes", async () => {
      mockVariables = [variable("mine", true), variable("other", true)];
      render(<GlobalVariablesPage />);
      await screen.findByText("OTHER");

      fireEvent.keyDown(cellOf("OTHER"), { key: "Enter" });
      fireEvent.click(
        await screen.findByRole("button", { name: "Close editor" }),
      );

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      await waitFor(() => expect(document.activeElement).toBe(cellOf("OTHER")));
    });

    it("should_delete_only_the_selected_row_and_report_a_failure", async () => {
      mockVariables = [variable("mine", true), variable("other", true)];
      render(<GlobalVariablesPage />);
      await screen.findByText("MINE");

      const checkbox = cellOf("MINE").querySelector<HTMLInputElement>(
        ".ag-selection-checkbox input",
      ) as HTMLInputElement;
      fireEvent.click(checkbox);
      const deleteButton = await screen.findByTestId("delete-row-button");
      await waitFor(() => expect(deleteButton).toBeEnabled());
      fireEvent.click(deleteButton);

      await waitFor(() =>
        expect(mockDeleteVariable).toHaveBeenCalledWith(
          { id: "mine" },
          expect.any(Object),
        ),
      );
      expect(mockDeleteVariable).toHaveBeenCalledTimes(1);
      act(() => mockDeleteVariable.mock.calls[0][1].onError());
      expect(mockSetErrorData).toHaveBeenCalledWith(
        expect.objectContaining({ list: [expect.stringContaining("MINE")] }),
      );
    });

    it("should_not_delete_a_selected_row_once_the_filter_hides_it", async () => {
      mockVariables = [variable("mine", true), variable("other", true)];
      let hideOther = false;
      mockListFilter.mockImplementation(
        (_type: string, items: GlobalVariable[]) => ({
          items: hideOther
            ? items.filter((item) => item.id !== "other")
            : items,
          tools: null,
        }),
      );
      const { rerender } = render(<GlobalVariablesPage />);
      await screen.findByText("OTHER");
      for (const name of ["MINE", "OTHER"]) {
        fireEvent.click(
          cellOf(name).querySelector(
            ".ag-selection-checkbox input",
          ) as HTMLInputElement,
        );
      }
      await settle();
      // Positive control: with both rows visible the selection is deletable.
      expect(screen.getByTestId("delete-row-button")).toBeEnabled();

      hideOther = true;
      rerender(<GlobalVariablesPage />);
      await waitFor(() =>
        expect(nameCells().map((cell) => cell.textContent?.trim())).toEqual([
          "MINE",
        ]),
      );
      await settle();
      fireEvent.click(screen.getByTestId("delete-row-button"));
      await settle();

      // New rowData drops the grid selection, so nothing hidden can go.
      expect(screen.getByTestId("delete-row-button")).toBeDisabled();
      expect(mockDeleteVariable).not.toHaveBeenCalled();
    });
  });

  describe("access column layout", () => {
    it("should_let_rows_grow_for_a_wrapped_label_but_keep_a_45px_floor", async () => {
      mockUseLabelSeam = true;
      mockVariables = [variable("mine", true), variable("shared", false)];
      render(<GlobalVariablesPage />);
      await screen.findByText("MINE");

      for (const cell of cellsIn("access")) {
        // autoHeight is what lets a two-to-four line label fit (QA LE-2566).
        expect(cell).toHaveClass("ag-cell-auto-height");
        const box = within(cell).getByTestId("variable-access-cell");
        // 45px row less 2 x 0.675rem padding and 2 x 1px border.
        expect(box).toHaveClass(
          "min-h-[calc(45px-1.35rem-2px)]",
          "items-center",
        );
      }
    });
  });
});
