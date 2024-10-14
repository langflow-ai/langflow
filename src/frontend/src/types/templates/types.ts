import { FlowType } from "@/types/flow";

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
  spiralImage: string;
  icon: string;
  category: string;
  title: string;
  description: string;
  flow: FlowType | undefined;
}

export interface TemplateCategoryProps {
  currentTab: NavItem;
  examples: any[];
  onCardClick: (example: any) => void;
}

export interface TemplateContentProps {
  currentTab: string;
  categories: NavItem[];
}

export interface TemplateCardComponentProps {
  example: {
    name: string;
    description: string;
    icon?: string;
    id: string;
    gradient?: string;
  };
  onClick: () => void;
}

export interface NavProps {
  links: NavItem[];
  currentTab: string;
  onClick?: (id: string) => void;
}
