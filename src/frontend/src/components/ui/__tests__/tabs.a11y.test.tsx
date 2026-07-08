import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "@/utils/a11y-test";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../tabs";

const renderTabs = () =>
  render(
    <Tabs defaultValue="flows">
      <TabsList>
        <TabsTrigger value="flows">Flows</TabsTrigger>
        <TabsTrigger value="components">Components</TabsTrigger>
      </TabsList>
      <TabsContent value="flows">Flows content</TabsContent>
      <TabsContent value="components">Components content</TabsContent>
    </Tabs>,
  );

describe("Tabs accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = renderTabs();

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_tablist_and_tab_roles_with_selection", () => {
    renderTabs();

    expect(screen.getByRole("tablist")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Flows" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "Components" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("should_move_selection_with_arrow_keys", async () => {
    const user = userEvent.setup();
    renderTabs();

    act(() => {
      screen.getByRole("tab", { name: "Flows" }).focus();
    });
    await user.keyboard("{ArrowRight}");

    expect(screen.getByRole("tab", { name: "Components" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
});
