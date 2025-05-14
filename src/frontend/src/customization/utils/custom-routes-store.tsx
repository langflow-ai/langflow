import { StoreGuard } from "@/components/authorization/storeGuard";
import StoreApiKeyPage from "@/pages/SettingsPage/pages/StoreApiKeyPage";
import StorePage from "@/pages/StorePage";
import { Route } from "react-router-dom";

export const CustomRoutesStore = () => {
  return (
    <>
      <Route path="store" element={<StoreApiKeyPage />} />
    </>
  );
};

export default CustomRoutesStore;
