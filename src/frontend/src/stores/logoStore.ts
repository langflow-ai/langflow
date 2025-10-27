import { create } from "zustand";
import { persist } from "zustand/middleware";

interface LogoStoreType {
  logoUrl: string | null;
  setLogoUrl: (url: string | null) => void;
  clearLogo: () => void;
}

const useLogoStore = create<LogoStoreType>()(
  persist(
    (set) => ({
      logoUrl: null,
      setLogoUrl: (url) => {
        set({ logoUrl: url });
        if (url) {
          localStorage.setItem("customLogoUrl", url);
        } else {
          localStorage.removeItem("customLogoUrl");
        }
      },
      clearLogo: () => {
        set({ logoUrl: null });
        localStorage.removeItem("customLogoUrl");
      },
    }),
    {
      name: "logo-storage",
    }
  )
);

export default useLogoStore;
