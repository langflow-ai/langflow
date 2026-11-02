import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import i18n from "@/i18n";
import ConnectionSetupHelp from "../components/ConnectionSetupHelp";
import { suggestedCallbackUrl } from "../helpers/setup-guide";

jest.unmock("react-i18next");
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

const help = (
  providerId: string,
  noRegistration = true,
  usesToken = false,
  docsUrl?: string | null,
) => (
  <I18nextProvider i18n={i18n}>
    <ConnectionSetupHelp
      key={`${providerId}:${usesToken}`}
      providerId={providerId}
      noRegistration={noRegistration}
      usesToken={usesToken}
      docsUrl={docsUrl}
    />
  </I18nextProvider>
);

describe("connection setup guidance", () => {
  afterEach(() => jest.restoreAllMocks());

  it.each([
    [
      "google",
      "https://docs.langflow.org/connection-oauth#customer-owned-google-registration",
    ],
    ["microsoft", "https://docs.langflow.org/entra-app-registration"],
    [
      "slack",
      "https://docs.langflow.org/connection-oauth#customer-owned-slack-registration",
    ],
  ])(
    "links %s to its setup guide even when a registration exists",
    (provider, url) => {
      render(help(provider, false));
      const link = screen.getByRole("link", { name: "Setup guide" });
      expect(link).toHaveAttribute("href", url);
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
      expect(
        screen.queryByTestId("connection-callback-url"),
      ).not.toBeInTheDocument();
    },
  );

  it("copies the suggested URI and clears confirmation when the provider changes", async () => {
    const user = userEvent.setup();
    const write = jest.spyOn(navigator.clipboard, "writeText");
    const { rerender } = render(help("google"));
    expect(
      screen.getByText(/LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS/),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Copy redirect URI" }));
    expect(write).toHaveBeenCalledWith(
      `${window.location.origin}/api/v1/connections/oauth/google/callback`,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Redirect URI copied.",
    );
    rerender(help("microsoft"));
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
    expect(screen.getByTestId("connection-callback-url")).toHaveTextContent(
      "/oauth/microsoft/callback",
    );
  });

  it("keeps the URI available for manual copying when clipboard access fails", async () => {
    const user = userEvent.setup();
    jest
      .spyOn(navigator.clipboard, "writeText")
      .mockRejectedValue(new Error("Denied"));
    render(help("google"));
    await user.click(screen.getByRole("button", { name: "Copy redirect URI" }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "Select and copy it manually.",
    );
    expect(screen.getByTestId("connection-callback-url")).toBeVisible();
  });

  it("does not require OAuth registration for a pasted Slack token", () => {
    render(help("slack", true, true));
    expect(screen.getByRole("link", { name: "Setup guide" })).toHaveAttribute(
      "href",
      "https://docs.langflow.org/bundles-slack#two-executing-identities",
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS/),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("connection-callback-url"),
    ).not.toBeInTheDocument();
  });

  it("does not invent setup links or callbacks for other providers", () => {
    render(help("custom-provider"));
    expect(screen.getByRole("alert")).toBeVisible();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("connection-callback-url"),
    ).not.toBeInTheDocument();
  });

  it("uses provider setup documentation without requiring OAuth for a pasted token", () => {
    const url = "https://docs.example.com/github/setup";
    render(help("github", true, true, url));
    expect(screen.getByRole("link", { name: "Setup guide" })).toHaveAttribute(
      "href",
      url,
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("connection-callback-url"),
    ).not.toBeInTheDocument();
  });

  it("preserves tailored setup documentation when provider metadata also supplies a URL", () => {
    render(help("slack", true, true, "https://docs.example.com/slack"));
    expect(screen.getByRole("link", { name: "Setup guide" })).toHaveAttribute(
      "href",
      "https://docs.langflow.org/bundles-slack#two-executing-identities",
    );
  });

  it.each([
    "javascript:alert(1)",
    "data:text/html,setup",
    "file:///setup.html",
    "//docs.example.com/setup",
    "/setup",
    "not a URL",
    "https://user:password@docs.example.com/setup", // pragma: allowlist secret
    "https://user@docs.example.com/setup",
    "",
    null,
  ])("does not render unsafe or missing documentation %s", (url) => {
    render(help("custom-provider", false, true, url));
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});

describe("suggested callback URL", () => {
  it.each([
    "https://langflow.example",
    "https://langflow.example:8443",
    "http://localhost:7860",
    "http://127.0.0.1:7860",
    "http://[::1]:7860",
  ])("preserves the hostname and port of %s", (origin) => {
    expect(suggestedCallbackUrl("slack", origin)).toBe(
      `${origin}/api/v1/connections/oauth/slack/callback`,
    );
  });

  it.each([
    "null",
    "file:///app",
    "http://langflow.example",
    "app://localhost",
  ])("does not suggest a callback the broker rejects for %s", (origin) => {
    expect(suggestedCallbackUrl("google", origin)).toBeUndefined();
  });

  it("does not build a callback for an unsupported provider", () => {
    expect(
      suggestedCallbackUrl("custom-provider", "https://langflow.example"),
    ).toBeUndefined();
  });
});
