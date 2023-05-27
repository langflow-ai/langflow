const template: { [char: string]: string } = {};

export type TemplateContextType = {
  templates: typeof template;
  setTemplates: (newState: {}) => void;
};
