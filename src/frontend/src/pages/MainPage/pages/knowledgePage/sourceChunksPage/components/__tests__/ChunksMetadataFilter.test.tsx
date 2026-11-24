import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

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
    // biome-ignore lint/suspicious/noExplicitAny: legacy
    useGetKbMetadataKeys: (params: any, options?: any) =>
      mockUseGetKbMetadataKeys(params, options),
  }),
);

import { ChunksMetadataFilter } from "../ChunksMetadataFilter";

const mockRefetch = jest.fn();
// biome-ignore lint/suspicious/noExplicitAny: legacy
const setHookData = (data: any, isLoading = false) => {
  mockUseGetKbMetadataKeys.mockReturnValue({
    data,
    isLoading,
    refetch: mockRefetch,
  });
};

beforeAll(() => {
  // cmdk calls scrollIntoView on selection; jsdom does not implement it.
  Element.prototype.scrollIntoView = jest.fn();
});

beforeEach(() => {
  mockUseGetKbMetadataKeys.mockReset();
  mockRefetch.mockReset();
  setHookData({ keys: {}, truncated: false });
});

const openFilterPopover = async () => {
  const user = userEvent.setup();
  await user.click(screen.getByTestId("chunks-metadata-add-filter"));
  return user;
};

describe("ChunksMetadataFilter", () => {
  it("renders the popover trigger labelled 'Filter by metadata'", () => {
    render(<ChunksMetadataFilter kbName="kb1" onAdd={jest.fn()} />);
    expect(screen.getByTestId("chunks-metadata-add-filter")).toHaveTextContent(
      "Filter by metadata",
    );
  });

  it("renders key combobox options when the key combobox opens", async () => {
    setHookData({
      keys: { year: ["2020", "2021"], dept: ["eng", "qa"] },
      truncated: false,
    });
    render(<ChunksMetadataFilter kbName="kb1" onAdd={jest.fn()} />);
    const user = await openFilterPopover();
    await user.click(screen.getByTestId("chunks-metadata-filter-key"));

    expect(
      await screen.findByTestId("chunks-metadata-filter-key-option-year"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("chunks-metadata-filter-key-option-dept"),
    ).toBeInTheDocument();
  });

  it("renders value combobox options for the selected key", async () => {
    setHookData({
      keys: { year: ["2020", "2021"], dept: ["eng"] },
      truncated: false,
    });
    render(<ChunksMetadataFilter kbName="kb1" onAdd={jest.fn()} />);
    const user = await openFilterPopover();

    await user.click(screen.getByTestId("chunks-metadata-filter-key"));
    await user.click(
      await screen.findByTestId("chunks-metadata-filter-key-option-year"),
    );
    await user.click(screen.getByTestId("chunks-metadata-filter-value"));

    expect(
      await screen.findByTestId("chunks-metadata-filter-value-option-2020"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("chunks-metadata-filter-value-option-2021"),
    ).toBeInTheDocument();
  });

  it("renders the empty-state hint when no keys are available", async () => {
    setHookData({ keys: {}, truncated: false });
    render(<ChunksMetadataFilter kbName="kb1" onAdd={jest.fn()} />);
    await openFilterPopover();
    expect(
      await screen.findByTestId("chunks-metadata-filter-empty"),
    ).toBeInTheDocument();
  });

  it("renders the truncated hint when the server caps any value list", async () => {
    setHookData({ keys: { tag: ["a"] }, truncated: true });
    render(<ChunksMetadataFilter kbName="kb1" onAdd={jest.fn()} />);
    await openFilterPopover();
    expect(
      await screen.findByTestId("chunks-metadata-filter-truncated"),
    ).toBeInTheDocument();
  });

  it("rejects an uppercase key (typed as custom) with the validation message", async () => {
    setHookData({ keys: {}, truncated: false });
    const onAdd = jest.fn();
    render(<ChunksMetadataFilter kbName="kb1" onAdd={onAdd} />);
    const user = await openFilterPopover();

    await user.click(screen.getByTestId("chunks-metadata-filter-key"));
    await user.type(
      screen.getByTestId("chunks-metadata-filter-key-input"),
      "Year",
    );
    await user.click(
      await screen.findByTestId("chunks-metadata-filter-key-custom"),
    );

    await user.click(screen.getByTestId("chunks-metadata-filter-value"));
    await user.type(
      screen.getByTestId("chunks-metadata-filter-value-input"),
      "2020",
    );
    await user.click(
      await screen.findByTestId("chunks-metadata-filter-value-custom"),
    );

    await user.click(screen.getByTestId("chunks-metadata-filter-submit"));
    expect(onAdd).not.toHaveBeenCalled();
    expect(
      screen.getByText(/1-32 lowercase letters, digits, or underscores/i),
    ).toBeInTheDocument();
  });

  it("refetches metadata keys every time the popover is opened", async () => {
    setHookData({ keys: { year: ["2020"] }, truncated: false });
    render(<ChunksMetadataFilter kbName="kb1" onAdd={jest.fn()} />);
    const user = await openFilterPopover();
    expect(mockRefetch).toHaveBeenCalledTimes(1);

    await user.keyboard("{Escape}");
    await user.click(screen.getByTestId("chunks-metadata-add-filter"));
    expect(mockRefetch).toHaveBeenCalledTimes(2);
  });

  it("calls onAdd with selected key/value on valid submit", async () => {
    setHookData({
      keys: { year: ["2020", "2021"] },
      truncated: false,
    });
    const onAdd = jest.fn();
    render(<ChunksMetadataFilter kbName="kb1" onAdd={onAdd} />);
    const user = await openFilterPopover();

    await user.click(screen.getByTestId("chunks-metadata-filter-key"));
    await user.click(
      await screen.findByTestId("chunks-metadata-filter-key-option-year"),
    );

    await user.click(screen.getByTestId("chunks-metadata-filter-value"));
    await user.click(
      await screen.findByTestId("chunks-metadata-filter-value-option-2020"),
    );

    await user.click(screen.getByTestId("chunks-metadata-filter-submit"));
    expect(onAdd).toHaveBeenCalledWith("year", "2020");
  });
});
