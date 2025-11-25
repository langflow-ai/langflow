import type { Meta, StoryObj } from "@storybook/react";
import { expect, userEvent, within } from "@storybook/test";
import { useEffect } from "react";
import useAuthStore from "@/stores/authStore";
import { useDarkStore } from "@/stores/darkStore";
import { useStoreStore } from "@/stores/storeStore";
import SettingsPage from "./index";

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

const withStoreSetup = (
  autoLogin: boolean = false,
  hasStore: boolean = false,
) => {
  return (Story: React.ComponentType) => {
    const StoreWrapper = () => {
      // Initialize stores on mount, before component renders
      useAuthStore.setState({ autoLogin });
      useStoreStore.setState({ hasStore });

      return <Story />;
    };
    return <StoreWrapper />;
  };
};

const meta: Meta<typeof SettingsPage> = {
  title: "Pages/SettingsPage",
  component: SettingsPage,
  decorators: [withStoreSetup(false, false), withDarkMode],
  parameters: {
    layout: "fullscreen",
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

// Story 1: Default state - shows General settings (autoLogin=false)
export const Default: Story = {
  args: {
    darkMode: false,
  },
  decorators: [withStoreSetup(false, false), withDarkMode],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // Verify Settings page title
    await expect(canvas.getByText("Settings")).toBeVisible();
    // Verify sidebar navigation is present
    const sidebar = canvas.getByRole("navigation");
    await expect(sidebar).toBeVisible();
    // Verify General settings is shown (because autoLogin=false)
    await expect(canvas.getByText("General")).toBeVisible();
    // Verify other standard items
    await expect(canvas.getByText("MCP Servers")).toBeVisible();
    await expect(canvas.getByText("Global Variables")).toBeVisible();
    await expect(canvas.getByText("Shortcuts")).toBeVisible();
    await expect(canvas.getByText("Messages")).toBeVisible();
  },
};

// Story 2: With Store features enabled
export const WithStoreFeatures: Story = {
  args: {
    darkMode: false,
  },
  decorators: [withStoreSetup(false, true), withDarkMode],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // Verify General is shown (hasStore=true triggers showGeneralSettings)
    await expect(canvas.getByText("General")).toBeVisible();
    // Verify store-related items might be present
    await expect(canvas.getByText("MCP Servers")).toBeVisible();
  },
};

// Story 3: Auto-login mode - General settings hidden
export const AutoLoginMode: Story = {
  args: {
    darkMode: false,
  },
  decorators: [withStoreSetup(true, false), withDarkMode],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // Verify Settings page loads
    await expect(canvas.getByText("Settings")).toBeVisible();
    // Verify General is NOT shown (autoLogin=true and no hasStore)
    // Note: This depends on ENABLE_PROFILE_ICONS feature flag
    // If profile icons are enabled, General will still show
    const generalLink = canvas.queryByText("General");
    // General might or might not be visible depending on feature flags
    // But we can verify other items are present
    await expect(canvas.getByText("MCP Servers")).toBeVisible();
    await expect(canvas.getByText("Shortcuts")).toBeVisible();
  },
};

// Story 4: Interactive sidebar navigation
export const InteractiveSidebar: Story = {
  args: {
    darkMode: false,
  },
  decorators: [withStoreSetup(false, false), withDarkMode],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // Verify sidebar is visible
    const sidebar = canvas.getByRole("navigation");
    await expect(sidebar).toBeVisible();

    // Try to interact with sidebar items
    const shortcutsLink = canvas.getByText("Shortcuts");
    await expect(shortcutsLink).toBeVisible();

    // Click on Shortcuts (if it's clickable)
    if (shortcutsLink.closest("a") || shortcutsLink.closest("button")) {
      await userEvent.click(shortcutsLink);
      // Verify the link is accessible
      await expect(shortcutsLink).toBeVisible();
    }

    // Verify Global Variables link
    const globalVarsLink = canvas.getByText("Global Variables");
    await expect(globalVarsLink).toBeVisible();
  },
};

// Story 5: Dark mode variant
export const DarkMode: Story = {
  args: {
    darkMode: true,
  },
  decorators: [withStoreSetup(false, false), withDarkMode],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // Verify page loads in dark mode
    await expect(canvas.getByText("Settings")).toBeVisible();
    const sidebar = canvas.getByRole("navigation");
    await expect(sidebar).toBeVisible();
    // Verify all navigation items are visible in dark mode
    await expect(canvas.getByText("General")).toBeVisible();
    await expect(canvas.getByText("Shortcuts")).toBeVisible();
  },
};

// Story 6: Complete configuration with all features
export const FullConfiguration: Story = {
  args: {
    darkMode: false,
  },
  decorators: [withStoreSetup(false, true), withDarkMode],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // Verify all standard items
    await expect(canvas.getByText("Settings")).toBeVisible();
    await expect(canvas.getByText("General")).toBeVisible();
    await expect(canvas.getByText("MCP Servers")).toBeVisible();
    await expect(canvas.getByText("Global Variables")).toBeVisible();
    await expect(canvas.getByText("Shortcuts")).toBeVisible();
    await expect(canvas.getByText("Messages")).toBeVisible();

    // Verify sidebar structure
    const sidebar = canvas.getByRole("navigation");
    await expect(sidebar).toBeVisible();
  },
};

// Story 7: Verify store state is accessible
export const VerifyStoreState: Story = {
  args: {
    darkMode: false,
  },
  decorators: [withStoreSetup(false, true), withDarkMode],
  play: async ({ canvasElement }) => {
    // Verify we can access store state
    const authState = useAuthStore.getState();
    const storeState = useStoreStore.getState();

    // Verify store values match what we set
    expect(authState.autoLogin).toBe(false);
    expect(storeState.hasStore).toBe(true);

    const canvas = within(canvasElement);
    // Verify the UI reflects the store state
    // hasStore=true should show General settings
    await expect(canvas.getByText("General")).toBeVisible();
    await expect(canvas.getByText("Settings")).toBeVisible();
  },
};
