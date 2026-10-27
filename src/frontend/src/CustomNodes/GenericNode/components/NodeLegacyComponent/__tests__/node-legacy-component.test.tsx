import { fireEvent, render, screen } from "@testing-library/react";
import { I18nextProvider, type I18nextProviderProps } from "react-i18next";
import en from "@/locales/en.json";
import fr from "@/locales/fr.json";
import { applyComponentFilter } from "@/pages/FlowPage/components/flowSidebarComponent/helpers/apply-component-filter";
import NodeLegacyComponent from "../index";

jest.unmock("react-i18next");

const mockData = {
  google: {
    "ext:google:GoogleSerperAPICore@official": {
      name: "GoogleSerperAPICore",
      display_name: "Google Serper API",
      template: {},
    },
    "ext:google:GoogleSearchAPICore@official": {
      name: "GoogleSearchAPICore",
      display_name: "Google Search API",
      template: {},
    },
  },
  data: {
    APIRequest: { display_name: "API Request", template: {} },
  },
};

const mockSetFilterComponent = jest.fn();

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: (selector: (state: unknown) => unknown) =>
    selector({ data: mockData }),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({
      setFilterComponent: mockSetFilterComponent,
      setFilterType: jest.fn(),
      setFilterEdge: jest.fn(),
    }),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    variant: _variant,
    size: _size,
    ...props
  }: {
    children: React.ReactNode;
    variant?: string;
    size?: unknown;
  }) => <button {...props}>{children}</button>,
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: unknown[]) => classes.filter(Boolean).join(" "),
}));

const testI18n = jest
  .requireActual<{
    createInstance: () => I18nextProviderProps["i18n"];
  }>("i18next")
  .createInstance();
void testI18n.init({
  lng: "en",
  fallbackLng: "en",
  initImmediate: false,
  resources: { en: { translation: en }, fr: { translation: fr } },
  interpolation: { escapeValue: false },
});

const renderBanner = (replacement?: string[], retiredIn?: string) =>
  render(
    <I18nextProvider i18n={testI18n}>
      <NodeLegacyComponent
        legacy
        replacement={replacement}
        retiredIn={retiredIn}
        setDismissAll={jest.fn()}
      />
    </I18nextProvider>,
  );

const hintText = () => screen.getByText(/^Use/).textContent;

describe("NodeLegacyComponent replacement hint", () => {
  beforeEach(() => {
    mockSetFilterComponent.mockClear();
    void testI18n.changeLanguage("en");
  });

  it("names extension-bundle replacements", () => {
    renderBanner(["google.GoogleSerperAPICore"]);

    expect(hintText()).toBe("Use Google Serper API.");
  });

  it("does not lead with a separator when the first replacement is unresolved", () => {
    renderBanner([
      "serpapi.Serp",
      "google.GoogleSerperAPICore",
      "data.APIRequest",
    ]);

    expect(hintText()).toBe("Use Google Serper API, API Request.");
  });

  it("reports no replacement when none resolve", () => {
    renderBanner(["serpapi.Serp", "searchapi.SearchComponent"]);

    expect(screen.getByText("No direct replacement.")).toBeInTheDocument();
    expect(screen.queryByText(/^Use/)).not.toBeInTheDocument();
  });

  it("filters the palette to the extension-bundle replacement on click", () => {
    renderBanner(["serpapi.Serp", "google.GoogleSerperAPICore"]);

    fireEvent.click(screen.getByRole("button", { name: "Google Serper API" }));

    expect(mockSetFilterComponent).toHaveBeenCalledWith(
      "google.ext:google:GoogleSerperAPICore@official",
    );
    // The palette filter matches palette keys exactly, so the key the banner
    // sends must select the replacement and nothing else.
    const [filterKey] = mockSetFilterComponent.mock.calls[0];
    const filtered = applyComponentFilter(mockData as never, filterKey);
    expect(Object.keys(filtered.google)).toEqual([
      "ext:google:GoogleSerperAPICore@official",
    ]);
    expect(filtered.data).toEqual({});
  });

  it("says a retired component fails and offers no dismiss", () => {
    renderBanner(["data.APIRequest"], "1.13.0");

    expect(
      screen.getByText(
        "Retired in 1.13.0. This component fails when the flow runs.",
      ),
    ).toBeInTheDocument();
    expect(hintText()).toBe("Use API Request.");
    expect(screen.queryByTestId("dismiss-warning-bar")).not.toBeInTheDocument();
  });

  it("translates the retirement warning in the selected language", async () => {
    await testI18n.changeLanguage("fr");

    renderBanner(["data.APIRequest"], "1.13.0");

    expect(screen.getByTestId("retired-component-bar")).toHaveTextContent(
      fr["node.retiredWarning"].replace("{{version}}", "1.13.0"),
    );
    expect(screen.getByTestId("retired-component-bar")).not.toHaveTextContent(
      "This component fails when the flow runs.",
    );
    expect(screen.queryByTestId("dismiss-warning-bar")).not.toBeInTheDocument();
  });

  it("filters the palette to a built-in replacement on click", () => {
    renderBanner(["data.APIRequest"]);

    fireEvent.click(screen.getByRole("button", { name: "API Request" }));

    expect(mockSetFilterComponent).toHaveBeenCalledWith("data.APIRequest");
  });
});
