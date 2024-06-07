import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedAdminRoute } from "./components/authAdminGuard";
import { ProtectedRoute } from "./components/authGuard";
import { ProtectedLoginRoute } from "./components/authLoginGuard";
import { CatchAllRoute } from "./components/catchAllRoutes";
import LoadingComponent from "./components/loadingComponent";
import { StoreGuard } from "./components/storeGuard";
import MessagesPage from "./pages/SettingsPage/pages/messagesPage";

const AdminPage = lazy(() => import("./pages/AdminPage"));
const LoginAdminPage = lazy(() => import("./pages/AdminPage/LoginPage"));
const ApiKeysPage = lazy(
  () => import("./pages/SettingsPage/pages/ApiKeysPage"),
);
const DeleteAccountPage = lazy(() => import("./pages/DeleteAccountPage"));
const FlowPage = lazy(() => import("./pages/FlowPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const MyCollectionComponent = lazy(
  () => import("./pages/MainPage/components/myCollectionComponent"),
);
const HomePage = lazy(() => import("./pages/MainPage/pages/mainPage"));
const PlaygroundPage = lazy(() => import("./pages/Playground"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const GeneralPage = lazy(
  () => import("./pages/SettingsPage/pages/GeneralPage"),
);
const GlobalVariablesPage = lazy(
  () => import("./pages/SettingsPage/pages/GlobalVariablesPage"),
);
const ShortcutsPage = lazy(
  () => import("./pages/SettingsPage/pages/ShortcutsPage"),
);
const SignUp = lazy(() => import("./pages/SignUpPage"));
const StorePage = lazy(() => import("./pages/StorePage"));
const ViewPage = lazy(() => import("./pages/ViewPage"));

const Router = () => {
  return (
    <Suspense
      fallback={
        <div className="loading-page-panel">
          <LoadingComponent remSize={50} />
        </div>
      }
    >
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
            element={
              <MyCollectionComponent key="components" type="component" />
            }
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
          <Route path="api-keys" element={<ApiKeysPage />} />
          <Route path="general/:scrollId?" element={<GeneralPage />} />
          <Route path="shortcuts" element={<ShortcutsPage />} />
          <Route path="messages" element={<MessagesPage />} />
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
          <Route
            path=""
            element={
              <ProtectedRoute>
                <PlaygroundPage />
              </ProtectedRoute>
            }
          />
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
        </Route>
      </Routes>
    </Suspense>
  );
};

export default Router;
