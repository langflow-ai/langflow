import type { Meta, StoryObj } from "@storybook/react";
import { expect, userEvent, within } from "@storybook/test";
import { useEffect } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import useAuthStore from "@/stores/authStore";
import { useDarkStore } from "@/stores/darkStore";
import { useStoreStore } from "@/stores/storeStore";
import SettingsPage from "./index";
import GeneralPage from "./pages/GeneralPage";
import GlobalVariablesPage from "./pages/GlobalVariablesPage";
import MCPServersPage from "./pages/MCPServersPage";
import MessagesPage from "./pages/messagesPage";
import ShortcutsPage from "./pages/ShortcutsPage";

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

const withRouter = (initialPath = "/settings/general") => {
  return () => {
    return (
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/settings" element={<SettingsPage />}>
            <Route path="general" element={<GeneralPage />} />
            <Route path="mcp-servers" element={<MCPServersPage />} />
            <Route path="global-variables" element={<GlobalVariablesPage />} />
            <Route path="shortcuts" element={<ShortcutsPage />} />
            <Route path="messages" element={<MessagesPage />} />
            <Route index element={<GeneralPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    );
  };
};

const withStoreSetup = (Story: React.ComponentType) => {
  const StoreWrapper = () => {
    useEffect(() => {
      // Initialize auth store
      useAuthStore.setState({
        autoLogin: false,
      });

      // Initialize store store
      useStoreStore.setState({
        hasStore: false,
      });
    }, []);

    return <Story />;
  };
  return <StoreWrapper />;
};

const meta: Meta<typeof SettingsPage> = {
  title: "Pages/SettingsPage",
  component: SettingsPage,
  decorators: [withStoreSetup, withDarkMode, withRouter("/settings/general")],
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

export const Default: Story = {
  args: {
    darkMode: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // Wait for page to load
    await expect(canvas.getByText("Settings")).toBeVisible();
    // Check sidebar is visible
    const sidebar = canvas.getByRole("navigation");
    await expect(sidebar).toBeVisible();
    // Check General page content is visible
    const generalLink = canvas.getByText("General");
    await expect(generalLink).toBeVisible();
  },
};

export const WithGeneralSettings: Story = {
  args: {
    darkMode: false,
  },
  decorators: [
    withRouter("/settings/general"),
    (Story) => {
      const StoreWrapper = () => {
        useEffect(() => {
          useAuthStore.setState({ autoLogin: false });
          useStoreStore.setState({ hasStore: true });
        }, []);
        return <Story />;
      };
      return <StoreWrapper />;
    },
    withDarkMode,
  ],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // Verify General settings section is visible
    await expect(canvas.getByText("General")).toBeVisible();
    // Check sidebar navigation
    const sidebar = canvas.getByRole("navigation");
    await expect(sidebar).toBeVisible();
  },
};

export const NavigateToShortcuts: Story = {
  args: {
    darkMode: false,
  },
  decorators: [withRouter("/settings/shortcuts"), withStoreSetup, withDarkMode],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // Verify Shortcuts page is loaded
    await expect(canvas.getByText("Shortcuts")).toBeVisible();
    // Check sidebar
    const shortcutsLink = canvas.getByText("Shortcuts");
    await expect(shortcutsLink).toBeVisible();
  },
};

export const NavigateToGlobalVariables: Story = {
  args: {
    darkMode: false,
  },
  decorators: [
    withRouter("/settings/global-variables"),
    withStoreSetup,
    withDarkMode,
  ],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // Verify Global Variables page is loaded
    const globalVarsLink = canvas.getByText("Global Variables");
    await expect(globalVarsLink).toBeVisible();
  },
};

export const DarkMode: Story = {
  args: {
    darkMode: true,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // Verify page loads in dark mode
    await expect(canvas.getByText("Settings")).toBeVisible();
    const sidebar = canvas.getByRole("navigation");
    await expect(sidebar).toBeVisible();
  },
};
