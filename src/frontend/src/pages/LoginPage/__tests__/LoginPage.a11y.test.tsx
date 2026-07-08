import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import useAlertStore from "@/stores/alertStore";
import { axe } from "@/utils/a11y-test";
import LoginPage from "../index";

const mockLoginMutate = jest.fn();

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
  useLoginUser: () => ({ mutate: mockLoginMutate }),
}));

jest.mock("@/customization/components/custom-link", () => ({
  CustomLink: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

jest.mock("@/hooks/use-sanitize-redirect-url", () => ({
  useSanitizeRedirectUrl: jest.fn(),
}));

function renderLoginPage() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <LoginPage />
    </QueryClientProvider>,
  );
}

describe("LoginPage accessibility", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useAlertStore.setState({
      notificationList: [],
      tempNotificationList: [],
    });
  });

  it("announces_required_field_errors_on_empty_submit", async () => {
    const user = userEvent.setup();
    renderLoginPage();

    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(
      await screen.findByText("Please enter your username"),
    ).toHaveAttribute("role", "alert");
    expect(screen.getByText("Please enter your password")).toHaveAttribute(
      "role",
      "alert",
    );
    expect(screen.getByPlaceholderText("Username")).toHaveAttribute(
      "aria-describedby",
      "login-username-error",
    );
    expect(screen.getByPlaceholderText("Password")).toHaveAttribute(
      "aria-describedby",
      "login-password-error",
    );
    expect(mockLoginMutate).not.toHaveBeenCalled();
  });

  it("should_have_no_axe_violations", async () => {
    const { container } = renderLoginPage();

    expect(await axe(container)).toHaveNoViolations();
  });

  it("uses_valid_external_labels_for_username_and_password", () => {
    renderLoginPage();

    expect(
      screen.getByRole("textbox", { name: /username/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText(/^Password/i, { selector: "input" }),
    ).toBeInTheDocument();
  });

  it("adds_actionable_suggestion_to_server_login_errors", () => {
    mockLoginMutate.mockImplementation((_user, options) => {
      options.onError({
        response: { data: { detail: "Incorrect username or password." } },
      });
    });
    const { container } = renderLoginPage();

    fireEvent.change(screen.getByPlaceholderText("Username"), {
      target: { value: "alice" },
    });
    fireEvent.change(screen.getByPlaceholderText("Password"), {
      target: { value: "wrong-password" },
    });
    fireEvent.submit(container.querySelector("form")!);

    expect(useAlertStore.getState().tempNotificationList[0]).toMatchObject({
      title: "Error signing in",
      type: "error",
      list: [
        "Incorrect username or password. Check your username and password, then try again.",
      ],
    });
  });

  it("preserves_fastapi_validation_error_details_for_login_errors", () => {
    mockLoginMutate.mockImplementation((_user, options) => {
      options.onError({
        response: {
          data: {
            detail: [
              { msg: "Username must be a string" },
              { msg: "Password is required" },
            ],
          },
        },
      });
    });
    const { container } = renderLoginPage();

    fireEvent.change(screen.getByPlaceholderText("Username"), {
      target: { value: "alice" },
    });
    fireEvent.change(screen.getByPlaceholderText("Password"), {
      target: { value: "wrong-password" },
    });
    fireEvent.submit(container.querySelector("form")!);

    expect(useAlertStore.getState().tempNotificationList[0]).toMatchObject({
      title: "Error signing in",
      type: "error",
      list: [
        "Username must be a string; Password is required. Check your username and password, then try again.",
      ],
    });
  });
});
