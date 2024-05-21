import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedAdminRoute } from "./components/authAdminGuard";
import { ProtectedRoute } from "./components/authGuard";
import { ProtectedLoginRoute } from "./components/authLoginGuard";
import { CatchAllRoute } from "./components/catchAllRoutes";
import { StoreGuard } from "./components/storeGuard";
import AdminPage from "./pages/AdminPage";
import LoginAdminPage from "./pages/AdminPage/LoginPage";
import ApiKeysPage from "./pages/ApiKeysPage";
import DeleteAccountPage from "./pages/DeleteAccountPage";
import FlowPage from "./pages/FlowPage";
import LoginPage from "./pages/LoginPage";
import MyCollectionComponent from "./pages/MainPage/components/myCollectionComponent";
import HomePage from "./pages/MainPage/pages/mainPage";
import PlaygroundPage from "./pages/Playground";
import SettingsPage from "./pages/SettingsPage";
import GeneralPage from "./pages/SettingsPage/pages/GeneralPage";
import GlobalVariablesPage from "./pages/SettingsPage/pages/GlobalVariablesPage";
import ShortcutsPage from "./pages/SettingsPage/pages/ShortcutsPage";
import SignUp from "./pages/SignUpPage";
import StorePage from "./pages/StorePage";
import ViewPage from "./pages/ViewPage";

const Router = () => {
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
        <Route index element={<Navigate replace to={"all"} />} />
        <Route
          path="flows/*"
          element={<MyCollectionComponent key="flows" type="flow" />}
        />
        <Route
          path="components/*"
          element={<MyCollectionComponent key="components" type="component" />}
        />
        <Route
          path="all/*"
          element={<MyCollectionComponent key="all" type="all" />}
        />
      </Route>
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate replace to={"general"} />} />
        <Route path="global-variables" element={<GlobalVariablesPage />} />
        <Route path="general" element={<GeneralPage />} />
        <Route path="shortcuts" element={<ShortcutsPage />} />
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
      <Route path="/playground/:id/">
        element=
        {
          <Route
            path=""
            element={
              <ProtectedRoute>
                <PlaygroundPage />
              </ProtectedRoute>
            }
          />
        }
      </Route>
      <Route path="/flow/:id/">
        <Route
          path="*"
          element={
            <ProtectedRoute>
              <FlowPage />
            </ProtectedRoute>
          }
        />
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
