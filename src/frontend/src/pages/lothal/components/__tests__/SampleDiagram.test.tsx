import { render, screen } from "@testing-library/react";
import { SampleDiagram } from "../SampleDiagram";

const participants = [
  { id: "user", label: "User" },
  { id: "api", label: "API" },
];
const messages = [
  { from: "user", to: "api", label: "request" },
  { from: "api", to: "user", label: "reply", dashed: true },
];

describe("SampleDiagram", () => {
  it("renders an accessible figure with the given title", () => {
    render(
      <SampleDiagram
        participants={participants}
        messages={messages}
        title="Order flow"
      />,
    );
    expect(screen.getByRole("img", { name: "Order flow" })).toBeInTheDocument();
  });

  it("renders every participant label and numbered message", () => {
    render(<SampleDiagram participants={participants} messages={messages} />);
    expect(screen.getByText("User")).toBeInTheDocument();
    expect(screen.getByText("API")).toBeInTheDocument();
    // Messages are numbered in order.
    expect(screen.getByText("1. request")).toBeInTheDocument();
    expect(screen.getByText("2. reply")).toBeInTheDocument();
  });

  it("falls back to a default accessible name when no title is given", () => {
    render(<SampleDiagram participants={participants} messages={messages} />);
    expect(
      screen.getByRole("img", { name: "Sequence diagram preview" }),
    ).toBeInTheDocument();
  });
});
