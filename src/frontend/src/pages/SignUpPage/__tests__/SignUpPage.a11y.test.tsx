import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import useAlertStore from "@/stores/alertStore";
import { axe } from "@/utils/a11y-test";
import SignUp from "../index";

const mockAddUserMutate = jest.fn();
const mockNavigate = jest.fn();

jest.mock("@/assets/LangflowLogo.svg?react", () => ({
  __esModule: true,
  default: (props: React.SVGProps<SVGSVGElement>) => <svg {...props} />,
}));

jest.mock("@radix-ui/react-form", () => {
  const React = require("react");
  return {
    __esModule: true,
    Root: ({ children, ...props }) =>
      React.createElement("form", props, children),
    Field: ({ children }) => React.createElement("div", null, children),
    Label: ({ children, ...props }) =>
      React.createElement("label", props, children),
    Control: ({ children }) => children,
    Message: ({ children, ...props }) =>
      React.createElement("p", props, children),
    Submit: ({ children }) => children,
  };
});

jest.mock("@/controllers/API/queries/auth", () => ({
  useAddUser: () => ({ mutate: mockAddUserMutate }),
}));

jest.mock("@/customization/components/custom-link", () => ({
  CustomLink: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => mockNavigate,
}));

jest.mock("@/customization/utils/analytics", () => ({
  track: jest.fn(),
}));

function renderSignUpPage() {
  return render(<SignUp />);
}

describe("SignUpPage accessibility", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useAlertStore.setState({
      notificationList: [],
      tempNotificationList: [],
    });
  });

  it("announces_required_field_errors_on_empty_submit", async () => {
    const user = userEvent.setup();
    renderSignUpPage();

    await user.click(screen.getByRole("button", { name: /sign up/i }));

    expect(
      await screen.findByText("Please enter your username"),
    ).toHaveAttribute("role", "alert");
    expect(screen.getByText("Please enter a password")).toHaveAttribute(
      "role",
      "alert",
    );
    expect(screen.getByText("Please confirm your password")).toHaveAttribute(
      "role",
      "alert",
    );
    expect(mockAddUserMutate).not.toHaveBeenCalled();
  });

  it("should_have_no_axe_violations", async () => {
    const { container } = renderSignUpPage();

    expect(await axe(container)).toHaveNoViolations();
  });

  it("uses_valid_external_labels_for_all_fields", () => {
    renderSignUpPage();

    expect(
      screen.getByRole("textbox", { name: /username/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/^Password/i)).toBeInTheDocument();
    expect(
      screen.getByLabelText(/^Confirm your password/i),
    ).toBeInTheDocument();
  });

  it("announces_actionable_password_mismatch_suggestion_after_confirm_blur", async () => {
    const user = userEvent.setup();
    renderSignUpPage();

    await user.type(screen.getByPlaceholderText("Password"), "first-password");
    await user.type(
      screen.getByPlaceholderText("Confirm your password"),
      "second-password",
    );

    expect(
      screen.queryByText(
        "Passwords do not match. Re-enter both passwords so they match.",
      ),
    ).not.toBeInTheDocument();

    fireEvent.blur(screen.getByPlaceholderText("Confirm your password"));

    const mismatch = await screen.findByText(
      "Passwords do not match. Re-enter both passwords so they match.",
    );
    expect(mismatch).toHaveAttribute("role", "alert");
    expect(screen.getByPlaceholderText("Password")).not.toHaveAttribute(
      "aria-describedby",
    );
    expect(
      screen.getByPlaceholderText("Confirm your password"),
    ).toHaveAttribute("aria-describedby", "signup-confirm-password-error");
  });

  it("adds_actionable_suggestion_to_server_signup_errors", () => {
    mockAddUserMutate.mockImplementation((_user, options) => {
      options.onError({
        response: { data: { detail: "This username is unavailable." } },
      });
    });
    const { container } = renderSignUpPage();

    fireEvent.change(screen.getByPlaceholderText("Username"), {
      target: { value: "alice" },
    });
    fireEvent.change(screen.getByPlaceholderText("Password"), {
      target: { value: "same-password" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm your password"), {
      target: { value: "same-password" },
    });
    fireEvent.submit(container.querySelector("form")!);

    expect(useAlertStore.getState().tempNotificationList[0]).toMatchObject({
      title: "Error signing up",
      type: "error",
      list: [
        "This username is unavailable. Use a different username or contact an administrator if you already have an account.",
      ],
    });
  });

  it("preserves_fastapi_validation_error_details_for_signup_errors", () => {
    mockAddUserMutate.mockImplementation((_user, options) => {
      options.onError({
        response: {
          data: {
            detail: [
              { msg: "Username must be unique" },
              { msg: "Password is too short" },
            ],
          },
        },
      });
    });
    const { container } = renderSignUpPage();

    fireEvent.change(screen.getByPlaceholderText("Username"), {
      target: { value: "alice" },
    });
    fireEvent.change(screen.getByPlaceholderText("Password"), {
      target: { value: "same-password" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm your password"), {
      target: { value: "same-password" },
    });
    fireEvent.submit(container.querySelector("form")!);

    expect(useAlertStore.getState().tempNotificationList[0]).toMatchObject({
      title: "Error signing up",
      type: "error",
      list: [
        "Username must be unique; Password is too short. Use a different username or contact an administrator if you already have an account.",
      ],
    });
  });
});
