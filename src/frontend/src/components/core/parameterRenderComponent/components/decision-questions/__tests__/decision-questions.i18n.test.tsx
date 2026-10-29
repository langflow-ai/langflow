import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import i18n, { loadLanguage } from "@/i18n";
import { mockGenericIconComponent } from "../../__tests__/a11y-mock-helpers";
import DecisionQuestionsComponent from "../decision-questions";

jest.unmock("react-i18next");
jest.mock("@/components/common/genericIconComponent", () =>
  mockGenericIconComponent(),
);
jest.mock("@/modals/tableModal", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

afterEach(async () => {
  await act(() => i18n.changeLanguage("en"));
});

it("shows translated Decision Types but saves the canonical one", async () => {
  await loadLanguage("de");
  await act(() => i18n.changeLanguage("de"));
  const handleOnNewValue = jest.fn();
  const question = { name: "", kind: "Choice", question: "Refund?" };
  render(
    <I18nextProvider i18n={i18n}>
      <DecisionQuestionsComponent
        id="questions"
        value={[question]}
        editNode={false}
        disabled={false}
        handleOnNewValue={handleOnNewValue}
      />
    </I18nextProvider>,
  );

  expect(screen.getByRole("tab", { name: "Auswahl" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await userEvent.setup().click(screen.getByRole("tab", { name: "Bewertung" }));
  expect(handleOnNewValue).toHaveBeenLastCalledWith({
    value: [{ ...question, kind: "Score" }],
  });
});
