import {Route, Routes} from "react-router-dom";
import {ProtectedAdminRoute} from "./components/authAdminGuard";
import {ProtectedRoute} from "./components/authGuard";
import {ProtectedLoginRoute} from "./components/authLoginGuard";
import {CatchAllRoute} from "./components/catchAllRoutes";
import AdminPage from "./pages/AdminPage";
import LoginAdminPage from "./pages/AdminPage/LoginPage";
import ApiKeysPage from "./pages/ApiKeysPage";
import CommunityPage from "./pages/CommunityPage";
import FlowPage from "./pages/FlowPage";
import HomePage from "./pages/MainPage";
import ProfileSettingsPage from "./pages/ProfileSettingsPage";
import ViewPage from "./pages/ViewPage";
import DeleteAccountPage from "./pages/deleteAccountPage";
import LoginPage from "./pages/loginPage";
import SignUp from "./pages/signUpPage";
import PaymentPage from "./pages/PaymentPage";
import {ProtectedPaymentRoute} from "./components/authPaymentGuard";

const Router = () => {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <ProtectedPaymentRoute>
                <HomePage />
            </ProtectedPaymentRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/community"
        element={
          <ProtectedRoute>
            <ProtectedPaymentRoute>
                <CommunityPage />
            </ProtectedPaymentRoute>
          </ProtectedRoute>
        }
      />
      <Route path="/flow/:id/">
        <Route
          path=""
          element={
            <ProtectedRoute>
              <ProtectedPaymentRoute>
                  <FlowPage />
              </ProtectedPaymentRoute>
            </ProtectedRoute>
          }
        />
        <Route
          path="view"
          element={
            <ProtectedRoute>
              <ProtectedPaymentRoute>
                  <ViewPage />
              </ProtectedPaymentRoute>
            </ProtectedRoute>
          }
        />
      </Route>
      <Route
        path="*"
        element={
          <ProtectedRoute>
            <ProtectedPaymentRoute>
                <CatchAllRoute />
            </ProtectedPaymentRoute>
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
        path="/payment"
        element={
          <ProtectedRoute>
            <PaymentPage />
          </ProtectedRoute>
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
