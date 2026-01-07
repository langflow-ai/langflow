export type Version = {
  name: string;
  url: string;
  description_section?: {
    section?: string;
    descriptions?: string[];
  }[];
  version_oss: string;
  is_lf_oss_update?: boolean;
  date?: string;
};

export type UpdaterStoreType = {
  openUpdaterModal: boolean;
  setOpenUpdaterModal: (open: boolean) => void;
  latestVersion: Version | null;
  versionApp: string | null;
  version_oss: string | null;
  showVersionChangelog: boolean;
  isLatestVersion: boolean;
};
