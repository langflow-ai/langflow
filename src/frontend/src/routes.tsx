import { lazy } from "react";
import {
  createBrowserRouter,
  createRoutesFromElements,
  Outlet,
  Route,
} from "react-router-dom";
import { ProtectedAdminRoute } from "./components/authorization/authAdminGuard";
import { ProtectedRoute } from "./components/authorization/authGuard";
import { ProtectedLoginRoute } from "./components/authorization/authLoginGuard";
import { AuthSettingsGuard } from "./components/authorization/authSettingsGuard";
import { StoreGuard } from "./components/authorization/storeGuard";
import ContextWrapper from "./contexts";
import { CustomNavigate } from "./customization/components/custom-navigate";
import { BASENAME } from "./customization/config-constants";
import {
  ENABLE_CUSTOM_PARAM,
  ENABLE_FILE_MANAGEMENT,
} from "./customization/feature-flags";
import { AppAuthenticatedPage } from "./pages/AppAuthenticatedPage";
import { AppInitPage } from "./pages/AppInitPage";
import { AppWrapperPage } from "./pages/AppWrapperPage";
import { DashboardWrapperPage } from "./pages/DashboardWrapperPage";
import FlowPage from "./pages/FlowPage";
import LoginPage from "./pages/LoginPage";
import CollectionPage from "./pages/MainPage/pages";
import FilesPage from "./pages/MainPage/pages/filesPage";
import HomePage from "./pages/MainPage/pages/homePage";
import SettingsPage from "./pages/SettingsPage";
import ApiKeysPage from "./pages/SettingsPage/pages/ApiKeysPage";
import GeneralPage from "./pages/SettingsPage/pages/GeneralPage";
import GlobalVariablesPage from "./pages/SettingsPage/pages/GlobalVariablesPage";
import MessagesPage from "./pages/SettingsPage/pages/messagesPage";
import ShortcutsPage from "./pages/SettingsPage/pages/ShortcutsPage";
import StoreApiKeyPage from "./pages/SettingsPage/pages/StoreApiKeyPage";
import StorePage from "./pages/StorePage";
import ViewPage from "./pages/ViewPage";

const AdminPage = lazy(() => import("./pages/AdminPage"));
const LoginAdminPage = lazy(() => import("./pages/AdminPage/LoginPage"));
const DeleteAccountPage = lazy(() => import("./pages/DeleteAccountPage"));

const PlaygroundPage = lazy(() => import("./pages/Playground"));

const SignUp = lazy(() => import("./pages/SignUpPage"));
const router = createBrowserRouter(
  createRoutesFromElements([
    <Route path="/playground/:id/">
      <Route
        path=""
        element={
          <ContextWrapper key={1}>
            <PlaygroundPage />
          </ContextWrapper>
        }
      />
    </Route>,
    <Route
      path={ENABLE_CUSTOM_PARAM ? "/:customParam?" : "/"}
      element={
        <ContextWrapper key={2}>
          <Outlet />
        </ContextWrapper>
      }
    >
      <Route path="" element={<AppInitPage />}>
        <Route path="" element={<AppWrapperPage />}>
          <Route
            path=""
            element={
              <ProtectedRoute>
                <Outlet />
              </ProtectedRoute>
            }
          >
            <Route path="" element={<AppAuthenticatedPage />}>
              <Route path="" element={<DashboardWrapperPage />}>
                <Route path="" element={<CollectionPage />}>
                  <Route
                    index
                    element={<CustomNavigate replace to={"flows"} />}
                  />
                  {ENABLE_FILE_MANAGEMENT && (
                    <Route path="files" element={<FilesPage />} />
                  )}
                  <Route
                    path="flows/"
                    element={<HomePage key="flows" type="flows" />}
                  >
                    <Route
                      path="folder/:folderId"
                      element={<HomePage key="flows" type="flows" />}
                    />
                  </Route>
                  <Route
                    path="components/"
                    element={<HomePage key="components" type="components" />}
                  >
                    <Route
                      path="folder/:folderId"
                      element={<HomePage key="components" type="components" />}
                    />
                  </Route>
                  <Route
                    path="all/"
                    element={<HomePage key="flows" type="flows" />}
                  >
                    <Route
                      path="folder/:folderId"
                      element={<HomePage key="flows" type="flows" />}
                    />
                  </Route>
                </Route>
                <Route path="settings" element={<SettingsPage />}>
                  <Route
                    index
                    element={<CustomNavigate replace to={"general"} />}
                  />
                  <Route
                    path="global-variables"
                    element={<GlobalVariablesPage />}
                  />
                  <Route path="api-keys" element={<ApiKeysPage />} />
                  <Route
                    path="general/:scrollId?"
                    element={
                      <AuthSettingsGuard>
                        <GeneralPage />
                      </AuthSettingsGuard>
                    }
                  />
                  <Route path="shortcuts" element={<ShortcutsPage />} />
                  <Route path="messages" element={<MessagesPage />} />
                  <Route path="store" element={<StoreApiKeyPage />} />
                </Route>
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
                <Route path="account">
                  <Route path="delete" element={<DeleteAccountPage />}></Route>
                </Route>
                <Route
                  path="admin"
                  element={
                    <ProtectedAdminRoute>
                      <AdminPage />
                    </ProtectedAdminRoute>
                  }
                />
              </Route>
              <Route path="flow/:id/">
                <Route path="" element={<DashboardWrapperPage />}>
                  <Route path="folder/:folderId/" element={<FlowPage />} />
                  <Route path="" element={<FlowPage />} />
                </Route>
                <Route path="view" element={<ViewPage />} />
              </Route>
            </Route>
          </Route>
          <Route
            path="login"
            element={
              <ProtectedLoginRoute>
                <LoginPage />
              </ProtectedLoginRoute>
            }
          />
          <Route
            path="signup"
            element={
              <ProtectedLoginRoute>
                <SignUp />
              </ProtectedLoginRoute>
            }
          />
          <Route
            path="login/admin"
            element={
              <ProtectedLoginRoute>
                <LoginAdminPage />
              </ProtectedLoginRoute>
            }
          />
        </Route>
      </Route>
      <Route path="*" element={<CustomNavigate replace to="/" />} />
    </Route>,
  ]),
  { basename: BASENAME || undefined },
);

export default router;
