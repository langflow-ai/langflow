import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

const mockUseGetKbMetadataKeys = jest.fn();
jest.mock(
  "@/controllers/API/queries/knowledge-bases/use-get-kb-metadata-keys",
  () => ({
    useGetKbMetadataKeys: (params: any, options?: any) =>
      mockUseGetKbMetadataKeys(params, options),
  }),
);

import { ChunksMetadataFilter } from "../ChunksMetadataFilter";

const mockRefetch = jest.fn();
const setHookData = (data: any, isLoading = false) => {
  mockUseGetKbMetadataKeys.mockReturnValue({
    data,
    isLoading,
    refetch: mockRefetch,
  });
};

beforeEach(() => {
  mockUseGetKbMetadataKeys.mockReset();
  mockRefetch.mockReset();
  setHookData({ keys: {}, truncated: false });
});

describe("ChunksMetadataFilter", () => {
  it("renders the popover trigger labelled 'Filter by metadata'", () => {
    render(<ChunksMetadataFilter kbName="kb1" onAdd={jest.fn()} />);
    expect(screen.getByTestId("chunks-metadata-add-filter")).toHaveTextContent(
      "Filter by metadata",
    );
  });

  it("populates the key datalist with available keys when popover opens", async () => {
    setHookData({
      keys: { year: ["2020", "2021"], dept: ["eng", "qa"] },
      truncated: false,
    });
    const user = userEvent.setup();
    render(<ChunksMetadataFilter kbName="kb1" onAdd={jest.fn()} />);

    await user.click(screen.getByTestId("chunks-metadata-add-filter"));

    await waitFor(() =>
      expect(
        screen.getByTestId("chunks-metadata-filter-key-options"),
      ).toBeInTheDocument(),
    );
    const options = screen
      .getByTestId("chunks-metadata-filter-key-options")
      .querySelectorAll("option");
    expect(
      Array.from(options)
        .map((o) => o.value)
        .sort(),
    ).toEqual(["dept", "year"]);
  });

  it("populates the value datalist with distinct values for the typed key", async () => {
    setHookData({
      keys: { year: ["2020", "2021"], dept: ["eng"] },
      truncated: false,
    });
    const user = userEvent.setup();
    render(<ChunksMetadataFilter kbName="kb1" onAdd={jest.fn()} />);

    await user.click(screen.getByTestId("chunks-metadata-add-filter"));
    await user.type(screen.getByTestId("chunks-metadata-filter-key"), "year");

    await waitFor(() =>
      expect(
        screen
          .getByTestId("chunks-metadata-filter-value-options")
          .querySelectorAll("option").length,
      ).toBe(2),
    );
    const values = Array.from(
      screen
        .getByTestId("chunks-metadata-filter-value-options")
        .querySelectorAll("option"),
    ).map((o) => o.value);
    expect(values).toEqual(["2020", "2021"]);
  });

  it("renders the empty-state hint when no keys are available", async () => {
    setHookData({ keys: {}, truncated: false });
    const user = userEvent.setup();
    render(<ChunksMetadataFilter kbName="kb1" onAdd={jest.fn()} />);
    await user.click(screen.getByTestId("chunks-metadata-add-filter"));
    expect(
      await screen.findByTestId("chunks-metadata-filter-empty"),
    ).toBeInTheDocument();
  });

  it("renders the truncated hint when the server caps any value list", async () => {
    setHookData({ keys: { tag: ["a"] }, truncated: true });
    const user = userEvent.setup();
    render(<ChunksMetadataFilter kbName="kb1" onAdd={jest.fn()} />);
    await user.click(screen.getByTestId("chunks-metadata-add-filter"));
    expect(
      await screen.findByTestId("chunks-metadata-filter-truncated"),
    ).toBeInTheDocument();
  });

  it("rejects an uppercase key with the validation message", async () => {
    const onAdd = jest.fn();
    const user = userEvent.setup();
    render(<ChunksMetadataFilter kbName="kb1" onAdd={onAdd} />);
    await user.click(screen.getByTestId("chunks-metadata-add-filter"));
    await user.type(screen.getByTestId("chunks-metadata-filter-key"), "Year");
    await user.type(screen.getByTestId("chunks-metadata-filter-value"), "2020");
    await user.click(screen.getByTestId("chunks-metadata-filter-submit"));
    expect(onAdd).not.toHaveBeenCalled();
    expect(
      screen.getByText(/1-32 lowercase letters, digits, or underscores/i),
    ).toBeInTheDocument();
  });

  it("refetches metadata keys every time the popover is opened", async () => {
    setHookData({ keys: { year: ["2020"] }, truncated: false });
    const user = userEvent.setup();
    render(<ChunksMetadataFilter kbName="kb1" onAdd={jest.fn()} />);

    await user.click(screen.getByTestId("chunks-metadata-add-filter"));
    expect(mockRefetch).toHaveBeenCalledTimes(1);
    // Close the popover by triggering the trigger again.
    await user.keyboard("{Escape}");
    await user.click(screen.getByTestId("chunks-metadata-add-filter"));
    expect(mockRefetch).toHaveBeenCalledTimes(2);
  });

  it("calls onAdd with trimmed key/value on valid submit and clears inputs", async () => {
    const onAdd = jest.fn();
    const user = userEvent.setup();
    render(<ChunksMetadataFilter kbName="kb1" onAdd={onAdd} />);
    await user.click(screen.getByTestId("chunks-metadata-add-filter"));
    await user.type(screen.getByTestId("chunks-metadata-filter-key"), "year");
    await user.type(screen.getByTestId("chunks-metadata-filter-value"), "2020");
    await user.click(screen.getByTestId("chunks-metadata-filter-submit"));
    expect(onAdd).toHaveBeenCalledWith("year", "2020");
  });
});
