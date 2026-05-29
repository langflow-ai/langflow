import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FormKeyRender } from "../form-key-render";

// These values match the en.json translations that the global i18n mock resolves.
const PRESET_WEEK = "1 week from today";
const PRESET_MONTH = "1 month from today";
const PRESET_YEAR = "1 year from today";

// Build props fresh per test to avoid shared mutable ref state.
const makeProps = (overrides = {}) => ({
  modalProps: {
    inputLabel: "Key name",
    inputPlaceholder: "Enter key name",
  },
  apiKeyName: "",
  // Cast avoids the tsx-generic-vs-JSX ambiguity when used outside a function.
  inputRef: { current: null } as React.RefObject<HTMLInputElement>,
  setApiKeyName: jest.fn(),
  expiresAt: "",
  setExpiresAt: jest.fn(),
  ...overrides,
});

describe("FormKeyRender", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the name input with label from modalProps", () => {
    render(<FormKeyRender {...makeProps()} />);
    expect(screen.getByText("Key name")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Enter key name")).toBeInTheDocument();
  });

  it("renders the expiration date input", () => {
    render(<FormKeyRender {...makeProps()} />);
    expect(document.querySelector('input[type="date"]')).toBeInTheDocument();
  });

  it("renders all three preset buttons", () => {
    render(<FormKeyRender {...makeProps()} />);
    expect(screen.getByText(PRESET_WEEK)).toBeInTheDocument();
    expect(screen.getByText(PRESET_MONTH)).toBeInTheDocument();
    expect(screen.getByText(PRESET_YEAR)).toBeInTheDocument();
  });

  it("calls setApiKeyName when the name input changes", async () => {
    const user = userEvent.setup();
    const setApiKeyName = jest.fn();
    render(<FormKeyRender {...makeProps({ setApiKeyName })} />);
    await user.type(screen.getByPlaceholderText("Enter key name"), "my-key");
    expect(setApiKeyName).toHaveBeenCalled();
  });

  it("calls setExpiresAt with a date string when a preset is clicked", async () => {
    const user = userEvent.setup();
    const setExpiresAt = jest.fn();
    render(<FormKeyRender {...makeProps({ setExpiresAt })} />);
    await user.click(screen.getByText(PRESET_WEEK));
    expect(setExpiresAt).toHaveBeenCalledWith(
      expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
    );
  });

  it("calls setExpiresAt with empty string when the active preset is clicked again", async () => {
    const user = userEvent.setup();
    const setExpiresAt = jest.fn();
    const d = new Date();
    d.setDate(d.getDate() + 7);
    const activeDate = d.toISOString().split("T")[0];
    render(
      <FormKeyRender {...makeProps({ expiresAt: activeDate, setExpiresAt })} />,
    );
    await user.click(screen.getByText(PRESET_WEEK));
    expect(setExpiresAt).toHaveBeenCalledWith("");
  });

  it("renders preset buttons even when modalProps is undefined", () => {
    render(<FormKeyRender {...makeProps({ modalProps: undefined })} />);
    expect(screen.getByText(PRESET_WEEK)).toBeInTheDocument();
    expect(screen.getByText(PRESET_YEAR)).toBeInTheDocument();
  });
});
