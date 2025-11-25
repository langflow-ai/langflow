import type { Meta, StoryObj } from "@storybook/react";
import { expect, within } from "@storybook/test";
import { useEffect } from "react";
import { MemoryRouter } from "react-router-dom";
import { useDarkStore } from "@/stores/darkStore";
import GlobalVariablesPage from "./index";

const withDarkMode = (
  Story: React.ComponentType,
  context: {
    args?: { darkMode?: boolean };
    parameters?: { darkMode?: boolean };
  },
) => {
  const DarkModeWrapper = () => {
    const dark =
      context.args?.darkMode || context.parameters?.darkMode === true;
    useEffect(() => {
      const body = document.getElementById("body") || document.body;
      if (dark) {
        body.classList.add("dark");
        useDarkStore.setState({ dark: true });
      } else {
        body.classList.remove("dark");
        useDarkStore.setState({ dark: false });
      }
    }, [dark]);
    return <Story />;
  };
  return <DarkModeWrapper />;
};

const withRouter = (Story: React.ComponentType) => {
  return (
    <MemoryRouter initialEntries={["/settings/global-variables"]}>
      <Story />
    </MemoryRouter>
  );
};

const meta: Meta<typeof GlobalVariablesPage> = {
  title: "Pages/SettingsPage/GlobalVariablesPage",
  component: GlobalVariablesPage,
  decorators: [withRouter, withDarkMode],
  parameters: {
    layout: "padded",
  },
  tags: ["autodocs"],
  argTypes: {
    darkMode: {
      control: "boolean",
      description: "Toggle dark mode",
      table: { category: "Theme" },
    },
  },
};

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    darkMode: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // Wait for page to load
    await expect(canvas.getByText("Global Variables")).toBeVisible();
    // Check Add New button
    const addButton = canvas.getByText("Add New");
    await expect(addButton).toBeVisible();
  },
};

export const DarkMode: Story = {
  args: {
    darkMode: true,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Global Variables")).toBeVisible();
  },
};
