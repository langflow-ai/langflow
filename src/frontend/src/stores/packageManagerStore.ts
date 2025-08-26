import { create } from "zustand";

interface PackageManagerState {
  isInstallingPackage: boolean;
  setIsInstallingPackage: (installing: boolean) => void;
  isBackendRestarting: boolean;
  setIsBackendRestarting: (restarting: boolean) => void;
  restartDetectedAt: number | null;
  setRestartDetectedAt: (timestamp: number | null) => void;
}

export const usePackageManagerStore = create<PackageManagerState>((set) => ({
  isInstallingPackage: false,
  setIsInstallingPackage: (installing) =>
    set({ isInstallingPackage: installing }),
  isBackendRestarting: false,
  setIsBackendRestarting: (restarting) =>
    set({ isBackendRestarting: restarting }),
  restartDetectedAt: null,
  setRestartDetectedAt: (timestamp) => set({ restartDetectedAt: timestamp }),
}));
