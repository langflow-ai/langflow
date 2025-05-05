import { StoreGuard } from "@/components/authorization/storeGuard";
import StoreApiKeyPage from "@/pages/SettingsPage/pages/StoreApiKeyPage";
import StorePage from "@/pages/StorePage";
import { Route } from "react-router-dom";

export const customRoutesStorePages = () => {
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

export default customRoutesStorePages;
