import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider, type I18nextProviderProps } from "react-i18next";
import de from "@/locales/de.json";
import en from "@/locales/en.json";
import es from "@/locales/es.json";
import fr from "@/locales/fr.json";
import ja from "@/locales/ja.json";
import ko from "@/locales/ko.json";
import pt from "@/locales/pt.json";
import zh from "@/locales/zh-Hans.json";
import FlowList from "../FlowList";
import { Failure } from "../RunCheck";
import { report } from "./fixture";

jest.unmock("react-i18next");

const locales = [
  ["en", en, "Deployments: deployment-1 · Triggers: trigger-1"],
  ["de", de, "Bereitstellungen: deployment-1 · Trigger: trigger-1"],
  ["es", es, "Despliegues: deployment-1 · Activadores: trigger-1"],
  ["fr", fr, "Déploiements : deployment-1 · Déclencheurs : trigger-1"],
  ["ja", ja, "デプロイ: deployment-1 · トリガー: trigger-1"],
  ["ko", ko, "배포: deployment-1 · 트리거: trigger-1"],
  ["pt", pt, "Implantações: deployment-1 · Gatilhos: trigger-1"],
  ["zh-Hans", zh, "部署：deployment-1 · 触发器：trigger-1"],
] as const;

it.each(locales)(
  "localizes deployment and trigger labels in %s",
  async (locale, messages, expected) => {
    const i18n = jest
      .requireActual<{
        createInstance: () => I18nextProviderProps["i18n"];
      }>("i18next")
      .createInstance();
    await i18n.init({
      lng: locale,
      resources: { [locale]: { translation: messages } },
    });
    render(
      <I18nextProvider i18n={i18n}>
        <FlowList
          flows={[
            {
              ...report.document.flows[0],
              used_by: {
                deployments: ["deployment-1"],
                triggers: ["trigger-1"],
              },
            },
          ]}
          selected={new Set()}
          onSelect={jest.fn()}
        />
      </I18nextProvider>,
    );
    await userEvent.click(
      screen.getByText(messages["settings.upgrade.flowDetails"]),
    );

    expect(
      screen.getByText((content) => content.includes(expected)),
    ).toBeVisible();
    expect(
      screen.queryByText(/deployments deployment-1/),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/triggers trigger-1/)).not.toBeInTheDocument();
  },
);

async function localized(locale: string, messages: Record<string, string>) {
  const i18n = jest
    .requireActual<{
      createInstance: () => I18nextProviderProps["i18n"];
    }>("i18next")
    .createInstance();
  await i18n.init({
    lng: locale,
    fallbackLng: false,
    resources: { [locale]: { translation: messages } },
  });
  return i18n;
}

it.each(locales)(
  "has copy in %s for every code the check can fail with",
  async (locale, messages) => {
    const i18n = await localized(locale, messages);
    const codes = [
      "unsupported_upgrade_report_format",
      "subprocess_unavailable",
    ];
    for (const code of codes) {
      const { unmount } = render(
        <I18nextProvider i18n={i18n}>
          <Failure run={{ kind: "failed", code, message: "server said" }} />
        </I18nextProvider>,
      );
      expect(screen.getByRole("alert")).toHaveTextContent(
        messages[`settings.upgrade.check.error.${code}`],
      );
      expect(screen.getByRole("alert")).not.toHaveTextContent("server said");
      unmount();
    }
  },
);

it("shows what the server said for a code the page has no copy for", async () => {
  const i18n = await localized("en", en);
  render(
    <I18nextProvider i18n={i18n}>
      <Failure
        run={{ kind: "failed", code: "new_code", message: "Something new." }}
      />
    </I18nextProvider>,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("Something new.");
});
