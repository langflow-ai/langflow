import { lazy } from "react";
import { Route } from "react-router-dom";
import { AuthorizationAdminRoute } from "../components/authorization-admin-route";
import { CustomNavigate } from "../components/custom-navigate";

const TeamsPage = lazy(() => import("@/pages/TeamsPage"));
const SharedWithMePage = lazy(() => import("@/pages/SharedWithMePage"));
const AdminPage = lazy(() => import("@/pages/admin"));

export const CustomRoutesStorePages = () => {
  return (
    <>
      <Route
        path="admin"
        element={
          <AuthorizationAdminRoute requiresCollaboration={false}>
            <AdminPage />
          </AuthorizationAdminRoute>
        }
      />
      <Route path="teams" element={<TeamsPage />} />
      <Route path="shared-with-me" element={<SharedWithMePage />} />
      <Route
        path="admin/teams"
        element={<CustomNavigate replace to="/admin?tab=teams" />}
      />
    </>
  );
};

export default CustomRoutesStorePages;
