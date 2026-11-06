import type { ReactNode } from "react";

/**
 * Title, description, and optional primary action, laid out like the Admin
 * page headers: the action stays on the right and centers on a one-line
 * description.
 */
export default function SettingsPageHeader({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex w-full shrink-0 flex-wrap items-start justify-between gap-4">
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <h2
          className="text-lg font-semibold tracking-tight"
          data-testid="settings_menu_header"
        >
          {title}
        </h2>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {children ? (
        <div className="mt-2 flex shrink-0 items-center gap-2">{children}</div>
      ) : null}
    </div>
  );
}
