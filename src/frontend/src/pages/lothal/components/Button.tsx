// Dockyard button. Five variants over the lothal theme tokens. A button atom
// scoped to the lothal surface — distinct from Langflow's `@/components/ui/button`.

import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from "react";

export type ButtonVariant =
  | "primary"
  | "accent"
  | "secondary"
  | "ghost"
  | "outline";
export type ButtonSize = "sm" | "md" | "lg";

export type ButtonProps = {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children?: ReactNode;
} & ButtonHTMLAttributes<HTMLButtonElement>;

const VARIANTS: Record<ButtonVariant, CSSProperties> = {
  primary: {
    background: "var(--ink)",
    color: "var(--paper)",
    borderColor: "var(--ink)",
  },
  accent: {
    background: "var(--accent)",
    color: "#fff",
    borderColor: "var(--accent)",
  },
  secondary: {
    background: "var(--surface)",
    color: "var(--ink)",
    borderColor: "var(--border-strong)",
  },
  ghost: {
    background: "transparent",
    color: "var(--ink-mute)",
    borderColor: "transparent",
  },
  outline: {
    background: "transparent",
    color: "var(--ink)",
    borderColor: "var(--border-strong)",
  },
};

export function Button({
  variant = "secondary",
  size = "md",
  children,
  disabled,
  style,
  ...rest
}: ButtonProps) {
  const base: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    height: size === "sm" ? 28 : size === "lg" ? 40 : 34,
    padding: size === "sm" ? "0 10px" : size === "lg" ? "0 18px" : "0 14px",
    fontSize: size === "sm" ? 12.5 : 13.5,
    fontWeight: 500,
    border: "1px solid transparent",
    borderRadius: 8,
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.5 : 1,
    transition:
      "background .15s ease, border-color .15s ease, transform .08s ease",
    whiteSpace: "nowrap",
    fontFamily: "var(--sans)",
  };
  return (
    <button
      type="button"
      disabled={disabled}
      style={{ ...base, ...VARIANTS[variant], ...style }}
      onMouseEnter={(e) => {
        if (!disabled) e.currentTarget.style.transform = "translateY(-0.5px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "translateY(0)";
      }}
      {...rest}
    >
      {children}
    </button>
  );
}
