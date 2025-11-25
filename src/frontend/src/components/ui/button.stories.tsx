import type { ArgTypes, Meta, StoryObj } from "@storybook/react";
import { expect, userEvent, within } from "@storybook/test";
import { useEffect } from "react";
import { useDarkStore } from "@/stores/darkStore";
import ForwardedIconComponent from "../common/genericIconComponent";
import type { ButtonProps } from "./button";
import { Button } from "./button";

const withDarkMode = (
  Story: React.ComponentType,
  context: {
    args?: { darkMode?: boolean } & ButtonProps;
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

const renderButton = (args: ButtonProps & { darkMode?: boolean }) => {
  const { darkMode, ...buttonProps } = args;
  return <Button {...buttonProps} />;
};

const playClickable = async (canvasElement: HTMLElement, text?: string) => {
  const canvas = within(canvasElement);
  const button = canvas.getByRole("button");
  if (text) await expect(button).toHaveTextContent(text);
  await expect(button).not.toBeDisabled();
  await userEvent.click(button);
  await expect(button).toBeVisible();
};

const playDisabled = async (canvasElement: HTMLElement, text: string) => {
  const canvas = within(canvasElement);
  const button = canvas.getByRole("button");
  await expect(button).toBeDisabled();
  await expect(button).toHaveTextContent(text);
  await userEvent.click(button);
  await expect(button).toBeDisabled();
};

const meta: Meta<typeof Button> = {
  title: "Design System/Button",
  component: Button,
  decorators: [withDarkMode],
  parameters: { layout: "padded" },
  tags: ["autodocs"],
  render: renderButton,
  argTypes: {
    variant: {
      control: "select",
      options: [
        "default",
        "destructive",
        "outline",
        "outlineAmber",
        "primary",
        "warning",
        "secondary",
        "ghost",
        "ghostActive",
        "menu",
        "menu-active",
        "link",
      ],
    },
    size: {
      control: "select",
      options: [
        "default",
        "md",
        "sm",
        "xs",
        "lg",
        "icon",
        "iconMd",
        "iconSm",
        "node-toolbar",
      ],
    },
    loading: { control: "boolean" },
    disabled: { control: "boolean" },
    // darkMode is a story-level control, not a Button prop
    darkMode: {
      control: "boolean",
      description: "Toggle dark mode",
      table: { category: "Theme" },
    },
  } as ArgTypes<ButtonProps & { darkMode?: boolean }>,
};

export default meta;
type Story = StoryObj<typeof meta>;

// Basic examples - use controls to explore variants/sizes
export const Default: Story = {
  args: { children: "Button", variant: "default", darkMode: false },
};
export const Primary: Story = {
  args: { children: "Primary Button", variant: "primary" },
  play: ({ canvasElement }) => playClickable(canvasElement, "Primary Button"),
};

export const WithIcon: Story = {
  args: {
    children: (
      <>
        <ForwardedIconComponent name="Plus" />
        Add Item
      </>
    ),
    variant: "default",
  },
  play: ({ canvasElement }) => playClickable(canvasElement, "Add Item"),
};

export const IconOnly: Story = {
  args: {
    children: <ForwardedIconComponent name="Settings" />,
    size: "icon",
    variant: "ghost",
  },
};

export const Loading: Story = {
  args: { children: "Loading...", loading: true },
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).getByRole("button")).toHaveTextContent(
      "Loading...",
    );
  },
};

export const Disabled: Story = {
  args: { children: "Disabled Button", disabled: true },
  play: ({ canvasElement }) => playDisabled(canvasElement, "Disabled Button"),
};

// Showcases
// Showcases - use CompleteShowcase for full overview
export const AllVariants: Story = {
  render: () => {
    const variants = [
      "default",
      "primary",
      "secondary",
      "destructive",
      "outline",
      "outlineAmber",
      "warning",
      "ghost",
      "ghostActive",
      "menu",
      "menu-active",
      "link",
    ] as const;
    return (
      <div className="flex flex-wrap gap-4">
        {variants.map((variant) => (
          <Button key={variant} variant={variant}>
            {variant.charAt(0).toUpperCase() +
              variant.slice(1).replace(/-/g, " ")}
          </Button>
        ))}
      </div>
    );
  },
};

export const CompleteShowcase: Story = {
  render: () => {
    const sections = [
      {
        title: "Variants",
        buttons: [
          { variant: "default" },
          { variant: "primary" },
          { variant: "secondary" },
          { variant: "destructive" },
          { variant: "outline" },
          { variant: "ghost" },
          { variant: "link" },
        ],
      },
      {
        title: "Sizes",
        buttons: [
          { size: "xs", label: "XS" },
          { size: "sm", label: "Small" },
          { size: "md", label: "Medium" },
          { size: "default", label: "Default" },
          { size: "lg", label: "Large" },
        ],
      },
      {
        title: "With Icons",
        buttons: [
          { icon: "Plus", label: "Add" },
          { variant: "outline", icon: "Download", label: "Download" },
          { variant: "ghost", size: "icon", icon: "Settings" },
        ],
      },
      {
        title: "States",
        buttons: [
          { label: "Normal" },
          { loading: true, label: "Loading" },
          { disabled: true, label: "Disabled" },
          { variant: "outline", disabled: true, label: "Disabled Outline" },
        ],
      },
    ];
    return (
      <div className="space-y-8">
        {sections.map(({ title, buttons }) => (
          <section key={title}>
            <h3 className="text-lg font-semibold mb-4">{title}</h3>
            <div className="flex flex-wrap gap-4">
              {buttons.map((props, i) => (
                <Button key={i} {...props}>
                  {props.icon && <ForwardedIconComponent name={props.icon} />}
                  {props.label || props.variant || props.size}
                </Button>
              ))}
            </div>
          </section>
        ))}
      </div>
    );
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const buttons = canvas.getAllByRole("button");
    await expect(buttons.length).toBeGreaterThan(0);
    const firstButton = buttons[0];
    if (firstButton && !firstButton.hasAttribute("disabled")) {
      await userEvent.click(firstButton);
      await expect(firstButton).toBeVisible();
    }
  },
};
