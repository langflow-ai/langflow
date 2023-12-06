import { useEffect } from "react";
import { Route, Routes, useNavigate } from "react-router-dom";
import { ProtectedAdminRoute } from "./components/authAdminGuard";
import { ProtectedRoute } from "./components/authGuard";
import { ProtectedLoginRoute } from "./components/authLoginGuard";
import { CatchAllRoute } from "./components/catchAllRoutes";
import { StoreGuard } from "./components/storeGuard";
import AdminPage from "./pages/AdminPage";
import LoginAdminPage from "./pages/AdminPage/LoginPage";
import ApiKeysPage from "./pages/ApiKeysPage";
import FlowPage from "./pages/FlowPage";
import HomePage from "./pages/MainPage";
import ComponentsComponent from "./pages/MainPage/components/components";
import ProfileSettingsPage from "./pages/ProfileSettingsPage";
import StorePage from "./pages/StorePage";
import ViewPage from "./pages/ViewPage";
import DeleteAccountPage from "./pages/deleteAccountPage";
import LoginPage from "./pages/loginPage";
import SignUp from "./pages/signUpPage";

const Router = () => {
  const navigate = useNavigate();
  useEffect(() => {
    // Redirect from root to /flows
    if (window.location.pathname === "/") {
      navigate("/flows");
    }
  }, [navigate]);
  return (
    <Routes>
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        }
      >
        <Route
          path="flows"
          element={<ComponentsComponent key="flows" is_component={false} />}
        />
        <Route
          path="components"
          element={<ComponentsComponent key="components" />}
        />
      </Route>
      <Route
        path="/store"
        element={
          <ProtectedRoute>
            <StoreGuard>
              <StorePage />
            </StoreGuard>
          </ProtectedRoute>
        }
      />
      <Route
        path="/store/:id/"
        element={
          <ProtectedRoute>
            <StoreGuard>
              <StorePage />
            </StoreGuard>
          </ProtectedRoute>
        }
      />

      <Route path="/flow/:id/">
        <Route
          path=""
          element={
            <ProtectedRoute>
              <FlowPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="view"
          element={
            <ProtectedRoute>
              <ViewPage />
            </ProtectedRoute>
          }
        />
      </Route>
      <Route
        path="*"
        element={
          <ProtectedRoute>
            <CatchAllRoute />
          </ProtectedRoute>
        }
      />

      <Route
        path="/login"
        element={
          <ProtectedLoginRoute>
            <LoginPage />
          </ProtectedLoginRoute>
        }
      />
      <Route
        path="/signup"
        element={
          <ProtectedLoginRoute>
            <SignUp />
          </ProtectedLoginRoute>
        }
      />
      <Route
        path="/login/admin"
        element={
          <ProtectedLoginRoute>
            <LoginAdminPage />
          </ProtectedLoginRoute>
        }
      />

      <Route
        path="/admin"
        element={
          <ProtectedAdminRoute>
            <AdminPage />
          </ProtectedAdminRoute>
        }
      />

      <Route path="/account">
        <Route
          path="settings"
          element={
            <ProtectedRoute>
              <ProfileSettingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="delete"
          element={
            <ProtectedRoute>
              <DeleteAccountPage />
            </ProtectedRoute>
          }
        ></Route>
        <Route
          path="api-keys"
          element={
            <ProtectedRoute>
              <ApiKeysPage />
            </ProtectedRoute>
          }
        ></Route>
      </Route>
    </Routes>
  );
};

export default Router;
