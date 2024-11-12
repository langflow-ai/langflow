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
  bgHorizontalImage: string;
  icon: string;
  category: string;
  flow: FlowType | undefined;
}

export interface TemplateCategoryProps {
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
  categories: Category[];
  currentTab: string;
  setCurrentTab: (id: string) => void;
}
