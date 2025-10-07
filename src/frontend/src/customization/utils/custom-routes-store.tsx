import { Route } from "react-router-dom";
import { StoreGuard } from "@/components/authorization/storeGuard";
import StoreApiKeyPage from "@/pages/SettingsPage/pages/StoreApiKeyPage";
import StorePage from "@/pages/StorePage";

export const CustomRoutesStore = () => {
  return (
    <>
      <Route path="store" element={<StoreApiKeyPage />} />
    </>
  );
};

export default CustomRoutesStore;
