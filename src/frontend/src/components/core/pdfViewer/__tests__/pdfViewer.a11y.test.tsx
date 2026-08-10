import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import PdfViewer from "../index";

jest.mock("react-pdf", () => ({
  pdfjs: { GlobalWorkerOptions: {}, version: "test" },
  Document: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="pdf-document">{children}</div>
  ),
  Page: () => <div data-testid="pdf-page" />,
}));

jest.mock("react-pdf/dist/esm/Page/AnnotationLayer.css", () => ({}), {
  virtual: true,
});
jest.mock("react-pdf/dist/esm/Page/TextLayer.css", () => ({}), {
  virtual: true,
});

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} aria-hidden="true" />
  ),
}));

describe("PdfViewer toolbar accessibility", () => {
  it.each([["Previous page"], ["Next page"], ["Zoom in"], ["Zoom out"]])(
    "should_name_the_%s_control",
    (name) => {
      render(<PdfViewer pdf="http://localhost/test.pdf" />);

      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    },
  );

  it("should_name_the_zoom_level_input", () => {
    render(<PdfViewer pdf="http://localhost/test.pdf" />);

    expect(
      screen.getByRole("spinbutton", { name: "Zoom level" }),
    ).toBeInTheDocument();
  });

  it("should_have_no_axe_violations", async () => {
    const { container } = render(<PdfViewer pdf="http://localhost/test.pdf" />);

    expect(await axe(container)).toHaveNoViolations();
  });
});
