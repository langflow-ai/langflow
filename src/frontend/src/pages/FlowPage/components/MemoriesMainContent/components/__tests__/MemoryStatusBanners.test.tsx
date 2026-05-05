import { render, screen } from "@testing-library/react";
import { MemoryStatusBanners } from "../MemoryStatusBanners";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <span>{name}</span>,
}));

describe("MemoryStatusBanners", () => {
  const baseMemory = {
    id: "m1",
    name: "Memory 1",
    status: "idle",
    total_messages_processed: 3,
    error_message: "",
  } as any;

  it("renders processing banner", () => {
    render(
      <MemoryStatusBanners
        memory={{ ...baseMemory, status: "generating" }}
        isProcessing
      />,
    );

    expect(screen.getByText("Generating memory...")).toBeInTheDocument();
    expect(screen.getByText("3 message(s) processed")).toBeInTheDocument();
  });

  it("renders failed banner", () => {
    render(
      <MemoryStatusBanners
        memory={{ ...baseMemory, status: "failed", error_message: "boom" }}
        isProcessing={false}
      />,
    );

    expect(screen.getByText("Update Failed")).toBeInTheDocument();
  });
});
