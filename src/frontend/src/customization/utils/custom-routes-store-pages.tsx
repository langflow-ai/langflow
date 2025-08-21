import { Route } from "react-router-dom";
import { StoreGuard } from "@/components/authorization/storeGuard";
import StoreApiKeyPage from "@/pages/SettingsPage/pages/StoreApiKeyPage";
import StorePage from "@/pages/StorePage";

export const CustomRoutesStorePages = () => {
  return (
    <>
      <Route
        path="store"
        element={
          <StoreGuard>
            <StorePage />
          </StoreGuard>
        }
      />
      <Route
        path="store/:id/"
        element={
          <StoreGuard>
            <StorePage />
          </StoreGuard>
        }
      />
    </>
  );
};

export default CustomRoutesStorePages;
