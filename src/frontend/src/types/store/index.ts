export type storeComponent = {
  id: string;
  is_component: boolean;
  tags?: { id: string; name: string }[];
  metadata?: any;
  downloads_count?: number;
  name: string;
  description: string;
  liked_by_count?: number;
  liked_by_user?: boolean;
  user_created?: { username: string };
  last_tested_version?: string;
  private?: boolean;
};

export type StoreComponentResponse = {
  count: number;
  authorized: boolean;
  results: storeComponent[];
};

export type shortcutsStoreType = {
  updateUniqueShortcut: (name: string, combination: string) => void;
  outputInspection: string;
  play: string;
  flow: string;
  group: string;
  cut: string;
  paste: string;
  api: string;
  openPlayground: string;
  undo: string;
  redo: string;
  advancedSettings: string;
  minimize: string;
  code: string;
  copy: string;
  duplicate: string;
  componentShare: string;
  docs: string;
  searchComponentsSidebar: string;
  changesSave: string;
  saveComponent: string;
  delete: string;
  update: string;
  download: string;
  freeze: string;
  toggleSidebar: string;
  freezePath: string;
  toolMode: string;
  shortcuts: Array<{
    name: string;
    display_name: string;
    shortcut: string;
  }>;
  setShortcuts: (
    newShortcuts: Array<{
      name: string;
      display_name: string;
      shortcut: string;
    }>,
  ) => void;
  getShortcutsFromStorage: () => void;
};
