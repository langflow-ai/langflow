import { fireEvent, render, screen } from "@testing-library/react";
import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import LinkComponent from "../index";

jest.mock("@/customization/utils/custom-open-new-tab", () => ({
  customOpenNewTab: jest.fn(),
}));

// The real icon is lazy-loaded and doesn't resolve synchronously in jsdom
// (renders nothing on the same tick), so icon-name assertions need a
// deterministic stand-in — same pattern used elsewhere in this codebase.
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

const mockCustomOpenNewTab = customOpenNewTab as jest.Mock;

const baseProps = {
  value: "example.com",
  disabled: false,
  id: "link-field",
  editNode: false,
  handleOnNewValue: jest.fn(),
};

describe("LinkComponent — opening the link", () => {
  beforeEach(() => jest.clearAllMocks());

  it("prepends https:// when the value has no protocol", () => {
    render(<LinkComponent {...baseProps} value="example.com" />);
    fireEvent.click(screen.getByTestId("link-field"));

    expect(mockCustomOpenNewTab).toHaveBeenCalledWith("https://example.com");
  });

  it("does not double-prepend when the value already has https://", () => {
    render(<LinkComponent {...baseProps} value="https://example.com" />);
    fireEvent.click(screen.getByTestId("link-field"));

    expect(mockCustomOpenNewTab).toHaveBeenCalledWith("https://example.com");
  });

  it("leaves an existing http:// protocol as-is", () => {
    render(<LinkComponent {...baseProps} value="http://example.com" />);
    fireEvent.click(screen.getByTestId("link-field"));

    expect(mockCustomOpenNewTab).toHaveBeenCalledWith("http://example.com");
  });

  it("matches the protocol check case-insensitively", () => {
    render(<LinkComponent {...baseProps} value="HTTPS://example.com" />);
    fireEvent.click(screen.getByTestId("link-field"));

    expect(mockCustomOpenNewTab).toHaveBeenCalledWith("HTTPS://example.com");
  });
});

describe("LinkComponent — disabled/empty-value states", () => {
  beforeEach(() => jest.clearAllMocks());

  // Adversarial: an empty value must not open a bare "https://" tab.
  it("does not call customOpenNewTab when value is empty", () => {
    render(<LinkComponent {...baseProps} value="" />);
    fireEvent.click(screen.getByTestId("link-field"));

    expect(mockCustomOpenNewTab).not.toHaveBeenCalled();
  });

  it("disables the button when value is empty, even if disabled is false", () => {
    render(<LinkComponent {...baseProps} value="" disabled={false} />);

    expect(screen.getByTestId("link-field")).toBeDisabled();
  });

  it("disables the button and blocks the click when disabled is true", () => {
    render(<LinkComponent {...baseProps} disabled={true} />);
    const button = screen.getByTestId("link-field");

    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(mockCustomOpenNewTab).not.toHaveBeenCalled();
  });
});

describe("LinkComponent — icon", () => {
  it("uses a custom icon name when provided", () => {
    render(<LinkComponent {...baseProps} icon="Globe" />);
    expect(screen.getByTestId("icon-Globe")).toBeInTheDocument();
  });

  it("falls back to the default icon when none is provided", () => {
    render(<LinkComponent {...baseProps} icon={undefined} />);
    expect(screen.getByTestId("icon-ExternalLink")).toBeInTheDocument();
  });
});
