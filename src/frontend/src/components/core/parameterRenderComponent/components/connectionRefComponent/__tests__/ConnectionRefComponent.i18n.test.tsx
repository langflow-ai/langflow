import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import type { ConnectionRead } from "@/controllers/API/queries/connections";
import i18n, { loadLanguage } from "@/i18n";
import ConnectionRefComponent from "../index";

jest.unmock("react-i18next");
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

const mockConnection: ConnectionRead = {
  id: "connection-1",
  owner_id: "user-1",
  ownership_mode: "user",
  provider_key: "google",
  name: "work",
  display_name: "Work",
  status: "ready",
  health: "healthy",
  granted_scopes: [],
  executing_identity: { identity: "user_delegated" },
  allow_non_interactive: false,
  has_credentials: true,
  health_checked_at: null,
  created_at: "2026-09-21T00:00:00Z",
  updated_at: "2026-09-21T00:00:00Z",
};

jest.mock("@/controllers/API/queries/connections/use-get-connections", () => ({
  useGetConnections: () => ({
    data: [mockConnection],
    isSuccess: true,
    refetch: jest.fn(),
  }),
}));

Element.prototype.scrollIntoView = jest.fn();

afterEach(async () => {
  await act(() => i18n.changeLanguage("en"));
});

it("translates the canvas picker and its scope feedback when the language changes", async () => {
  await loadLanguage("pt");
  const user = userEvent.setup();
  render(
    <I18nextProvider i18n={i18n}>
      <ConnectionRefComponent
        id="connection-picker"
        value=""
        editNode={false}
        disabled={false}
        handleOnNewValue={jest.fn()}
        provider="google"
        requiredScopes={["gmail.send"]}
      />
    </I18nextProvider>,
  );
  expect(screen.getByRole("combobox")).toHaveAccessibleName(
    "Select a google connection",
  );
  await user.click(screen.getByRole("combobox"));
  expect(screen.getByTestId("connection-option-google/work")).toHaveTextContent(
    "Missing gmail.send",
  );

  await act(() => i18n.changeLanguage("pt"));
  expect(screen.getByRole("combobox")).toHaveAccessibleName(
    "Selecione uma conexão de google",
  );
  expect(screen.getByTestId("connection-option-google/work")).toHaveTextContent(
    "Faltando: gmail.send",
  );
  expect(screen.getByText("Requer gmail.send")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Atualizar" })).toBeInTheDocument();
  expect(screen.queryByText("Refresh")).not.toBeInTheDocument();
});

it.each([
  ["en", "1 scope", "2 scopes"],
  ["de", "1 Berechtigung", "2 Berechtigungen"],
  ["es", "1 permiso", "2 permisos"],
  ["fr", "1 autorisation", "2 autorisations"],
  ["ja", "1 個のスコープ", "2 個のスコープ"],
  ["pt", "1 escopo", "2 escopos"],
  ["zh-Hans", "1 个权限范围", "2 个权限范围"],
])(
  "uses the real scope plural rules for %s",
  async (language, singular, plural) => {
    await loadLanguage(language);
    expect(
      i18n.t("connections.scopes.count", { count: 1, lng: language }),
    ).toBe(singular);
    expect(
      i18n.t("connections.scopes.count", { count: 2, lng: language }),
    ).toBe(plural);
  },
);
