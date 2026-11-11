import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import FileCardWrapper from "../file-card-wrapper";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
  ForwardedIconComponent: () => null,
}));

jest.mock("@/customization/utils/urls", () => ({
  getBaseUrl: () => "http://localhost:3000/api/v1/",
}));

const renderWrapper = (path: Parameters<typeof FileCardWrapper>[0]["path"]) =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <FileCardWrapper index={0} path={path} />
    </QueryClientProvider>,
  );

describe("FileCardWrapper", () => {
  it("should_name_a_sent_file_as_uploaded_when_the_path_has_the_upload_timestamp", () => {
    renderWrapper("flow-1/2026-11-09_10-02-11_notes.txt");

    expect(screen.getAllByText("notes.txt").length).toBeGreaterThan(0);
    expect(screen.queryByText(/2026-11-09_10-02-11/)).not.toBeInTheDocument();
  });

  it("should_keep_an_explicit_file_name", () => {
    renderWrapper({
      path: "flow-1/2026-11-09_10-02-11_notes.txt",
      type: "txt",
      name: "2026-11-09_10-02-11_notes.txt",
    });

    expect(
      screen.getAllByText("2026-11-09_10-02-11_notes.txt").length,
    ).toBeGreaterThan(0);
  });
});
