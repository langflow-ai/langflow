import { create } from "zustand";

interface PackageManagerState {
  isInstallingPackage: boolean;
  setIsInstallingPackage: (installing: boolean) => void;
}

export const usePackageManagerStore = create<PackageManagerState>((set) => ({
  isInstallingPackage: false,
  setIsInstallingPackage: (installing) =>
    set({ isInstallingPackage: installing }),
}));
