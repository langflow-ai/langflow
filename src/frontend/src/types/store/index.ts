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
  group: string;
  cut: string;
  paste: string;
  api: string;
  open: string;
  undo: string;
  redo: string;
  advanced: string;
  minimize: string;
  code: string;
  copy: string;
  duplicate: string;
  share: string;
  docs: string;
  save: string;
  delete: string;
  shortcuts: Array<{
    name: string;
    shortcut: string;
  }>;
  unavailableShortcuts: string[];
  setShortcuts: (
    newShortcuts: Array<{ name: string; shortcut: string }>,
    unavailable: string[]
  ) => void;
};
