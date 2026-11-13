import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "@/utils/a11y-test";
import TriggerPayloadTree from "../TriggerPayloadTree";

describe("TriggerPayloadTree", () => {
  it("shows primitive types without dropping false, zero, null, or empty values", () => {
    render(
      <TriggerPayloadTree
        payload={{
          text: "Hello",
          enabled: false,
          count: 0,
          absent: null,
          empty: "",
          object: {},
          array: [],
        }}
      />,
    );

    expect(screen.getByText('"Hello"')).toBeInTheDocument();
    expect(screen.getByText("false")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.getByText("null", { exact: true })).toBeInTheDocument();
    expect(screen.getByText('""')).toBeInTheDocument();
    expect(screen.getByText("{}")).toBeInTheDocument();
    expect(screen.getByText("[]")).toBeInTheDocument();
    expect(screen.getAllByText("Text", { exact: true })).toHaveLength(2);
    expect(screen.getByText("Boolean")).toBeInTheDocument();
    expect(screen.getByText("Number")).toBeInTheDocument();
    expect(screen.getByText("Null", { exact: true })).toBeInTheDocument();
  });

  it("expands objects and arrays without flattening their fields", async () => {
    const user = userEvent.setup();
    render(
      <TriggerPayloadTree
        payload={{ messages: [{ sender: "Alice", text: "Hello" }, 0] }}
      />,
    );
    expect(screen.queryByText('"Alice"')).not.toBeInTheDocument();

    await user.click(screen.getByText("messages", { exact: true }));
    await user.click(screen.getByText("[0]", { exact: true }));

    const messages = screen
      .getByText("messages", { exact: true })
      .closest("details")!;
    expect(within(messages).getByText("sender")).toBeInTheDocument();
    expect(within(messages).getByText('"Alice"')).toBeInTheDocument();
    expect(within(messages).getByText("[1]")).toBeInTheDocument();
    expect(within(messages).getByText("0")).toBeInTheDocument();
    expect(screen.getByText("2 items")).toBeInTheDocument();
  });

  it("keeps native collection controls reachable by keyboard", async () => {
    const user = userEvent.setup();
    render(<TriggerPayloadTree payload={{ data: { sender: "Alice" } }} />);
    const data = screen.getByText("data", { exact: true }).closest("summary")!;

    await user.tab();
    await user.tab();

    expect(data).toHaveFocus();
  });

  it("removes nested values when a collection is collapsed", async () => {
    const user = userEvent.setup();
    render(<TriggerPayloadTree payload={{ data: { sender: "Alice" } }} />);

    await user.click(screen.getByText("data", { exact: true }));
    expect(await screen.findByText('"Alice"')).toBeInTheDocument();
    await user.click(screen.getByText("data", { exact: true }));

    expect(screen.queryByText('"Alice"')).not.toBeInTheDocument();
  });

  it("pages through large objects without losing later fields", async () => {
    const user = userEvent.setup();
    const payload = Object.fromEntries(
      Array.from({ length: 60 }, (_, index) => [`field${index}`, index]),
    );
    render(<TriggerPayloadTree payload={payload} />);
    expect(screen.getByText("field49")).toBeInTheDocument();
    expect(screen.queryByText("field59")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Show 10 more" }));

    expect(screen.getByText("field59")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Show .* more/ })).toBeNull();
  });

  it("can render a deeply nested payload without eagerly traversing it", () => {
    let payload: Record<string, unknown> = { leaf: "Deep value" };
    for (let depth = 0; depth < 10_000; depth++) payload = { child: payload };

    render(<TriggerPayloadTree payload={payload} />);

    expect(screen.getByText("child")).toBeInTheDocument();
    expect(screen.queryByText('"Deep value"')).toBeNull();
  });

  it("renders arbitrary field names and values as text", () => {
    const payload = JSON.parse(
      '{"__proto__":"kept","":"empty key","<img src=x onerror=alert(1)>":"<script>alert(1)</script>"}',
    );
    const { container } = render(<TriggerPayloadTree payload={payload} />);

    expect(screen.getByText("__proto__")).toBeInTheDocument();
    expect(screen.getByText('""')).toBeInTheDocument();
    expect(
      screen.getByText("<img src=x onerror=alert(1)>"),
    ).toBeInTheDocument();
    expect(screen.getByText('"<script>alert(1)</script>"')).toBeInTheDocument();
    expect(container.querySelector("img, script")).toBeNull();
  });

  it("preserves redacted values supplied by the event API", () => {
    render(<TriggerPayloadTree payload={{ token: "[REDACTED]" }} />);

    expect(screen.getByText('"[REDACTED]"')).toBeInTheDocument();
    expect(screen.queryByText("raw_request")).toBeNull();
  });

  it("keeps a long string available without truncating its value", () => {
    const text = "x".repeat(10_000);
    render(<TriggerPayloadTree payload={{ text }} />);

    expect(screen.getByText(JSON.stringify(text))).toBeInTheDocument();
  });

  it.each([null, undefined, false, 0, "", [], {}])(
    "handles an empty or scalar payload %p",
    (payload) => {
      render(<TriggerPayloadTree payload={payload} />);

      expect(
        screen.getByTestId("trigger-event-payload"),
      ).not.toBeEmptyDOMElement();
    },
  );

  it("shows an unexpected missing value without crashing", () => {
    render(<TriggerPayloadTree payload={{ value: undefined }} />);

    expect(screen.getByText("undefined")).toBeInTheDocument();
  });

  it("does not introduce accessibility violations", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <TriggerPayloadTree
        payload={{ data: { text: "Hello" }, values: [0, false, null] }}
      />,
    );
    await user.click(screen.getByText("data", { exact: true }));
    await user.click(screen.getByText("values", { exact: true }));

    expect(await axe(container)).toHaveNoViolations();
  });
});
