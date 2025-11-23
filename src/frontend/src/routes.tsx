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
import { ProtectedRoleRoute } from "./components/authorization/authRoleGuard";
import { AuthSettingsGuard } from "./components/authorization/authSettingsGuard";
import { USER_ROLES } from "./types/auth";
import ContextWrapper from "./contexts";
import CustomDashboardWrapperPage from "./customization/components/custom-DashboardWrapperPage";
import { CustomNavigate } from "./customization/components/custom-navigate";
import { BASENAME } from "./customization/config-constants";
import {
  ENABLE_CUSTOM_PARAM,
  ENABLE_FILE_MANAGEMENT,
  ENABLE_KNOWLEDGE_BASES,
} from "./customization/feature-flags";
import { CustomRoutesStore } from "./customization/utils/custom-routes-store";
import { CustomRoutesStorePages } from "./customization/utils/custom-routes-store-pages";
import { AppAuthenticatedPage } from "./pages/AppAuthenticatedPage";
import { AppInitPage } from "./pages/AppInitPage";
import { AppWrapperPage } from "./pages/AppWrapperPage";
import FlowPage from "./pages/FlowPage";
import LoginPage from "./pages/LoginPage";
import FilesPage from "./pages/MainPage/pages/filesPage";
import HomePage from "./pages/MainPage/pages/homePage";
import KnowledgePage from "./pages/MainPage/pages/knowledgePage";
import CollectionPage from "./pages/MainPage/pages/main-page";
import SettingsPage from "./pages/SettingsPage";
import AgentBuilderPage from "./pages/AgentBuilderPage";
import AgentMarketplacePage from "./pages/AgentMarketplacePage";
import AgentMarketplaceDetailPage from "./pages/AgentMarketplacePage/DetailPage";
import MarketplacePage from "./pages/MarketplacePage";
import MarketplaceDetailPage from "./pages/MarketplacePage/DetailPage";
import ApiKeysPage from "./pages/SettingsPage/pages/ApiKeysPage";
import GeneralPage from "./pages/SettingsPage/pages/GeneralPage";
import GlobalVariablesPage from "./pages/SettingsPage/pages/GlobalVariablesPage";
import MCPServersPage from "./pages/SettingsPage/pages/MCPServersPage";
import MessagesPage from "./pages/SettingsPage/pages/messagesPage";
import ShortcutsPage from "./pages/SettingsPage/pages/ShortcutsPage";
import ConversationPage from "./pages/AgentBuilderPage/ConversationPage";

const AdminPage = lazy(() => import("./pages/AdminPage"));
const LoginAdminPage = lazy(() => import("./pages/AdminPage/LoginPage"));
const DeleteAccountPage = lazy(() => import("./pages/DeleteAccountPage"));
const AllRequestsPage = lazy(() => import("./pages/AllRequestsPage"));

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
              <Route path="" element={<CustomDashboardWrapperPage />}>
                <Route path="" element={<CollectionPage />}>
                  <Route
                    index
                    element={<CustomNavigate replace to={"agent-builder"} />}
                  />
                  {ENABLE_FILE_MANAGEMENT && (
                    <Route path="assets">
                      <Route
                        index
                        element={<CustomNavigate replace to="files" />}
                      />
                      <Route path="files" element={<FilesPage />} />
                      {ENABLE_KNOWLEDGE_BASES && (
                        <Route
                          path="knowledge-bases"
                          element={<KnowledgePage />}
                        />
                      )}
                    </Route>
                  )}
                  <Route
                    path="agent-builder/"
                    element={<AgentBuilderPage key="agent-builder" />}
                  />
                  <Route
                    path="agent-marketplace/"
                    element={<AgentMarketplacePage />}
                  />
                  <Route
                    path="flows/"
                    element={<HomePage key="flows" type="flows" />}
                  />
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
                  <Route
                    path="mcp/"
                    element={<HomePage key="mcp" type="mcp" />}
                  >
                    <Route
                      path="folder/:folderId"
                      element={<HomePage key="mcp" type="mcp" />}
                    />
                  </Route>
                  <Route path="marketplace" element={<MarketplacePage />} />
                  <Route
                    path="marketplace/detail/:publishedFlowId"
                    element={<MarketplaceDetailPage />}
                  />
                </Route>
                <Route
                  path="agent-marketplace/detail/:flowId"
                  element={<AgentMarketplaceDetailPage />}
                />
                <Route path="settings" element={<SettingsPage />}>
                  <Route
                    index
                    element={<CustomNavigate replace to={"general"} />}
                  />
                  <Route
                    path="global-variables"
                    element={<GlobalVariablesPage />}
                  />
                  <Route path="mcp-servers" element={<MCPServersPage />} />
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
                  {CustomRoutesStore()}
                </Route>
                {CustomRoutesStorePages()}
                <Route path="agent-builder" element={<AgentBuilderPage />} />
                <Route
                  path="agent-builder/conversation/:sessionId"
                  element={<ConversationPage />}
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
                <Route
                  path="all-requests"
                  element={
                    <ProtectedRoleRoute requiredRoles={[USER_ROLES.MARKETPLACE_ADMIN]}>
                      <AllRequestsPage />
                    </ProtectedRoleRoute>
                  }
                />
              </Route>
              <Route path="flow/:id/">
                <Route path="" element={<CustomDashboardWrapperPage />}>
                  <Route path="folder/:folderId/" element={<FlowPage />} />
                  <Route path="" element={<FlowPage />} />
                </Route>
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
  { basename: BASENAME || undefined }
);

export default router;
