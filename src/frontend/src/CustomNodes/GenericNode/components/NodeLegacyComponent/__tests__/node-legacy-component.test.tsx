import { fireEvent, render, screen } from "@testing-library/react";
import { applyComponentFilter } from "@/pages/FlowPage/components/flowSidebarComponent/helpers/apply-component-filter";
import NodeLegacyComponent from "../index";

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

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
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

const renderBanner = (replacement?: string[]) =>
  render(
    <NodeLegacyComponent
      legacy
      replacement={replacement}
      setDismissAll={jest.fn()}
    />,
  );

const hintText = () => screen.getByText(/^Use/).textContent;

describe("NodeLegacyComponent replacement hint", () => {
  beforeEach(() => {
    mockSetFilterComponent.mockClear();
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

  it("filters the palette to a built-in replacement on click", () => {
    renderBanner(["data.APIRequest"]);

    fireEvent.click(screen.getByRole("button", { name: "API Request" }));

    expect(mockSetFilterComponent).toHaveBeenCalledWith("data.APIRequest");
  });
});
