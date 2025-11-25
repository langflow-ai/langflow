import type { Meta, StoryObj } from "@storybook/react";
import { expect, userEvent, within } from "@storybook/test";
import { useEffect } from "react";
import useAlertStore from "@/stores/alertStore";
import { useDarkStore } from "@/stores/darkStore";
import useFlowStore from "@/stores/flowStore";
import { useTypesStore } from "@/stores/typesStore";
import type { APIClassType } from "@/types/api";
import type { DropDownComponent } from "@/types/components";
import type { BaseInputProps } from "../parameterRenderComponent/types";
import Dropdown from "./index";

// Initialize stores with minimal mock data for Storybook
const withStoreSetup = (Story: React.ComponentType) => {
  const StoreWrapper = () => {
    useEffect(() => {
      // Initialize flowStore with empty nodes
      useFlowStore.setState({
        nodes: [],
        edges: [],
        getNode: () => null,
        setFilterEdge: () => {},
        setFilterType: () => {},
      });

      // Initialize typesStore with empty data
      useTypesStore.setState({
        data: [],
      });

      // Initialize alertStore (no initial state needed)
      useAlertStore.setState({
        setErrorData: () => {},
      });
    }, []);

    return <Story />;
  };
  return <StoreWrapper />;
};

const withDarkMode = (
  Story: React.ComponentType,
  context: {
    args?: { darkMode?: boolean } & DropDownComponent & BaseInputProps;
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

const mockNodeClass: APIClassType = {
  base_classes: [],
  description: "Mock component",
  display_name: "Mock Component",
  documentation: "",
  custom_fields: {},
  output_types: [],
  name: "MockComponent",
  beta: false,
  error: null,
  official: false,
  tags: [],
};

const defaultArgs: DropDownComponent & BaseInputProps = {
  value: "",
  options: ["Option 1", "Option 2", "Option 3", "Option 4", "Option 5"],
  onSelect: (value: string) => {
    console.log("Selected:", value);
  },
  nodeId: "mock-node-id",
  nodeClass: mockNodeClass,
  handleNodeClass: () => {},
  name: "testField",
  disabled: false,
  isLoading: false,
  editNode: false,
  placeholder: "Select an option...",
  helperText: "",
  hasRefreshButton: false,
};

const meta: Meta<typeof Dropdown> = {
  title: "Components/Dropdown",
  component: Dropdown,
  decorators: [withStoreSetup, withDarkMode],
  parameters: { layout: "padded" },
  tags: ["autodocs"],
  argTypes: {
    value: { control: "text" },
    options: { control: "object" },
    combobox: { control: "boolean" },
    disabled: { control: "boolean" },
    isLoading: { control: "boolean" },
    editNode: { control: "boolean" },
    placeholder: { control: "text" },
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
    ...defaultArgs,
    darkMode: false,
  },
};

export const WithValue: Story = {
  args: {
    ...defaultArgs,
    value: "Option 2",
    darkMode: false,
  },
};

export const Combobox: Story = {
  args: {
    ...defaultArgs,
    combobox: true,
    placeholder: "Type or select an option...",
    darkMode: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const trigger = canvas.getByRole("combobox");
    await userEvent.click(trigger);
    const input = canvas.getByPlaceholderText("Type or select an option...");
    await userEvent.type(input, "Custom Value");
    await expect(input).toHaveValue("Custom Value");
  },
};

export const WithMetadata: Story = {
  args: {
    ...defaultArgs,
    options: ["OpenAI", "Anthropic", "Cohere"],
    optionsMetaData: [
      { provider: "OpenAI", model: "gpt-4", status: "active" },
      { provider: "Anthropic", model: "claude-3", status: "active" },
      { provider: "Cohere", model: "command", status: "beta" },
    ],
    darkMode: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const trigger = canvas.getByRole("combobox");
    await userEvent.click(trigger);
    // Check that options are visible
    const option1 = canvas.getByText("OpenAI");
    await expect(option1).toBeVisible();
  },
};

export const Disabled: Story = {
  args: {
    ...defaultArgs,
    disabled: true,
    value: "Option 1",
    darkMode: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const trigger = canvas.getByRole("combobox");
    await expect(trigger).toBeDisabled();
  },
};

export const Loading: Story = {
  args: {
    ...defaultArgs,
    isLoading: true,
    darkMode: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // Check for loading indicator
    const loadingText = canvas.queryByText(/receiving/i);
    if (loadingText) {
      await expect(loadingText).toBeVisible();
    }
  },
};

export const ManyOptions: Story = {
  args: {
    ...defaultArgs,
    options: Array.from({ length: 50 }, (_, i) => `Option ${i + 1}`),
    darkMode: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const trigger = canvas.getByRole("combobox");
    await userEvent.click(trigger);
    // Verify scrolling works with many options
    const option50 = canvas.getByText("Option 50");
    await expect(option50).toBeVisible();
  },
};

export const Searchable: Story = {
  args: {
    ...defaultArgs,
    combobox: true,
    options: [
      "Python",
      "JavaScript",
      "TypeScript",
      "Java",
      "C++",
      "Go",
      "Rust",
      "Swift",
    ],
    placeholder: "Search languages...",
    darkMode: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const trigger = canvas.getByRole("combobox");
    await userEvent.click(trigger);
    const input = canvas.getByPlaceholderText("Search languages...");
    await userEvent.type(input, "Script");
    // Should filter to JavaScript and TypeScript
    await expect(canvas.getByText("JavaScript")).toBeVisible();
    await expect(canvas.getByText("TypeScript")).toBeVisible();
    await expect(canvas.queryByText("Python")).not.toBeInTheDocument();
  },
};

export const DarkMode: Story = {
  args: {
    ...defaultArgs,
    darkMode: true,
  },
};
