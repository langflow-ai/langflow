import { fireEvent, render, screen } from "@testing-library/react";
import EditFlowSettings from "../index";

jest.mock("@/components/ui/input", () => ({
  Input: ({ ...props }) => <input {...props} />,
}));
jest.mock("@/components/ui/textarea", () => ({
  Textarea: ({ ...props }) => <textarea {...props} />,
}));
jest.mock("@/components/ui/switch", () => ({
  Switch: ({ checked, onCheckedChange, ...rest }) => (
    <input
      role="switch"
      aria-checked={!!checked}
      type="checkbox"
      checked={!!checked}
      onChange={(e) => onCheckedChange?.(e.target.checked)}
      {...rest}
    />
  ),
}));
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => <span />,
}));
// Mock Radix Form to avoid context requirement
jest.mock("@radix-ui/react-form", () => ({
  __esModule: true,
  Field: ({ children }) => <div>{children}</div>,
  Label: ({ children }) => <label>{children}</label>,
  Control: ({ children }) => <>{children}</>,
  Message: ({ children }) => <div>{children}</div>,
  Root: ({ children }) => <form>{children}</form>,
}));

// Prevent importing utils that pull darkStore via side-effects
jest.mock("@/utils/utils", () => ({
  __esModule: true,
  cn: (...args) => args.filter(Boolean).join(" "),
}));

describe("EditFlowSettings", () => {
  it("validates name and shows messages", () => {
    const setName = jest.fn();
    render(
      <EditFlowSettings
        name=""
        description=""
        invalidNameList={["Taken"]}
        setName={setName}
        setDescription={jest.fn()}
      />,
    );

    const nameInput = screen.getByTestId("input-flow-name");
    fireEvent.change(nameInput, { target: { value: "T" } });
    expect(setName).toHaveBeenCalledWith("T");

    fireEvent.change(nameInput, { target: { value: "" } });
    expect(screen.getByText(/Please enter a name/)).toBeInTheDocument();

    fireEvent.change(nameInput, { target: { value: "Taken" } });
    expect(screen.getAllByText(/already exists/).length).toBeGreaterThan(0);
  });

  it("submits with Enter in description without Shift", () => {
    const submitForm = jest.fn();
    render(
      <EditFlowSettings
        name="Flow"
        description="Desc"
        submitForm={submitForm}
        setName={jest.fn()}
        setDescription={jest.fn()}
      />,
    );

    const desc = screen.getByTestId("input-flow-description");
    fireEvent.keyDown(desc, { key: "Enter", shiftKey: false });
    expect(submitForm).toHaveBeenCalled();
  });

  it("toggles lock switch", () => {
    const setLocked = jest.fn();
    render(
      <EditFlowSettings
        name="Flow"
        description="Desc"
        locked={false}
        setLocked={setLocked}
        setName={jest.fn()}
        setDescription={jest.fn()}
      />,
    );
    const sw = screen.getByTestId("lock-flow-switch");
    fireEvent.click(sw);
    expect(setLocked).toHaveBeenCalledWith(true);
  });
});
