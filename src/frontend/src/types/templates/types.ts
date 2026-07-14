import type { FlowType } from "@/types/flow";

export interface TeamTemplateSummary {
  id: string;
  name: string;
  description?: string | null;
  category: string;
  tags: string[];
  icon?: string | null;
  gradient?: string | null;
  source_flow_id?: string | null;
  workspace_id?: string | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
  source: "team";
}

export interface TeamTemplate extends TeamTemplateSummary {
  flow_data: FlowType["data"];
  schema_version: number;
  sanitizer_version: number;
}

export interface TeamTemplateList {
  items: TeamTemplateSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateTeamTemplatePayload {
  source_flow_id: string;
  name: string;
  description?: string;
  category: string;
  tags: string[];
}

export interface NavItem {
  title: string;
  icon: string;
  id: string;
}

export interface Category {
  title: string;
  items: NavItem[];
}

export interface CardData {
  bgImage: string;
  bgHorizontalImage: string;
  icon: string;
  category: string;
  flow: FlowType | undefined;
}

export interface TemplateCategoryProps {
  examples: TemplateExample[];
  onCardClick: (example: TemplateExample) => void;
}

export interface TemplateContentProps {
  currentTab: string;
  categories: NavItem[];
}

export type TemplateExample = FlowType & {
  source?: "system" | "team";
  created_by?: string | null;
  category?: string;
};

export interface TemplateCardComponentProps {
  example: TemplateExample;
  onClick: () => void;
  onDelete?: () => void;
}

export interface NavProps {
  categories: Category[];
  currentTab: string;
  setCurrentTab: (id: string) => void;
}
