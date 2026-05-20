import { create } from "zustand";

const STORAGE_KEY = "cloudOnly";

declare global {
  interface Window {
    __CLOUD_ONLY__?: boolean;
  }
}

const isLockedByEnv = (): boolean => {
  if (import.meta.env.VITE_CLOUD_ONLY === "true") return true;
  try {
    if (window.__CLOUD_ONLY__ === true) return true;
  } catch {
    // window may be unavailable in SSR
  }
  return false;
};

interface CloudModeStoreType {
  cloudOnly: boolean;
  isLocked: boolean;
  setCloudOnly: (value: boolean) => void;
}

export const useCloudModeStore = create<CloudModeStoreType>((set) => {
  const locked = isLockedByEnv();
  const initial = locked
    ? true
    : (() => {
        try {
          return window.localStorage.getItem(STORAGE_KEY) === "true";
        } catch {
          return false;
        }
      })();

  return {
    cloudOnly: initial,
    isLocked: locked,
    setCloudOnly: (value) => {
      if (locked) return;
      set({ cloudOnly: value });
      try {
        window.localStorage.setItem(STORAGE_KEY, value.toString());
      } catch {
        // localStorage may be unavailable in private browsing or SSR
      }
    },
  };
});
