import type { TemplateExample } from "@/types/templates/types";

const TEMPLATE_MANAGER_USERNAME = "langflow";

interface TemplateUser {
  id?: string;
  username?: string;
  is_superuser?: boolean;
}

export function canDeleteTeamTemplate(
  template: TemplateExample,
  user: TemplateUser | null | undefined,
): boolean {
  return (
    template.source === "team" &&
    (template.created_by === user?.id ||
      user?.is_superuser === true ||
      user?.username === TEMPLATE_MANAGER_USERNAME)
  );
}
