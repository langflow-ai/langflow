import type { Meta, StoryObj } from "@storybook/react";
import { useEffect } from "react";
import { MemoryRouter } from "react-router-dom";
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

const withRouter = (Story: React.ComponentType) => {
  return (
    <MemoryRouter initialEntries={["/settings"]}>
      <Story />
    </MemoryRouter>
  );
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
  decorators: [withRouter, withStoreSetup, withDarkMode],
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
};

export const WithGeneralSettings: Story = {
  args: {
    darkMode: false,
  },
  decorators: [
    withRouter,
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
};

export const DarkMode: Story = {
  args: {
    darkMode: true,
  },
};
