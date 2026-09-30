import React from "react";

const typeConfig: Record<string, { emoji: string; className: string }> = {
  info: { emoji: "ℹ️", className: "lf-callout--info" },
  warning: { emoji: "⚠️", className: "lf-callout--warning" },
  tip: { emoji: "💡", className: "lf-callout--tip" },
  note: { emoji: "📝", className: "lf-callout--note" },
};

interface CalloutProps {
  type?: "info" | "warning" | "tip" | "note";
  title?: string;
  children: React.ReactNode;
}

export default function Callout({
  type = "info",
  title,
  children,
}: CalloutProps) {
  const config = typeConfig[type] || typeConfig.info;

  return (
    <div className={`lf-callout ${config.className}`}>
      <div className="lf-callout-header">
        <span className="lf-callout-emoji">{config.emoji}</span>
        {title && <span className="lf-callout-title">{title}</span>}
      </div>
      <div className="lf-callout-body">{children}</div>
    </div>
  );
}
