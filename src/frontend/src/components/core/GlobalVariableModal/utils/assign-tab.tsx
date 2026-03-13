import { TAB_TYPES } from "@/types/global_variables";

const TAB_MAP: Record<string, TAB_TYPES> = {
  credential: "Credential",
  generic: "Generic",
};

export const assignTab = (tab: string): TAB_TYPES => {
  const normalizedTab = tab.toLowerCase().trim();
  return TAB_MAP[normalizedTab] ?? "Credential";
};
