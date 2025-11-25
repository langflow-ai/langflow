import type { Meta, StoryObj } from "@storybook/react";
import { expect, within } from "@storybook/test";
import { useEffect } from "react";
import { MemoryRouter } from "react-router-dom";
import { defaultShortcuts } from "@/constants/constants";
import { useDarkStore } from "@/stores/darkStore";
import { useShortcutsStore } from "@/stores/shortcuts";
import ShortcutsPage from "./index";

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
    <MemoryRouter initialEntries={["/settings/shortcuts"]}>
      <Story />
    </MemoryRouter>
  );
};

const withStoreSetup = (Story: React.ComponentType) => {
  const StoreWrapper = () => {
    useEffect(() => {
      // Initialize shortcuts store with default shortcuts
      useShortcutsStore.setState({
        shortcuts: defaultShortcuts,
      });
    }, []);

    return <Story />;
  };
  return <StoreWrapper />;
};

const meta: Meta<typeof ShortcutsPage> = {
  title: "Pages/SettingsPage/ShortcutsPage",
  component: ShortcutsPage,
  decorators: [withRouter, withStoreSetup, withDarkMode],
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
    // Wait for table to load
    await expect(canvas.getByText("Shortcuts")).toBeVisible();
    // Check table headers
    await expect(canvas.getByText("Functionality")).toBeVisible();
    await expect(canvas.getByText("Keyboard Shortcut")).toBeVisible();
    // Check Restore button
    await expect(canvas.getByText("Restore")).toBeVisible();
  },
};

export const DarkMode: Story = {
  args: {
    darkMode: true,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Shortcuts")).toBeVisible();
    await expect(canvas.getByText("Functionality")).toBeVisible();
  },
};
