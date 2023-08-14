import { Route, Routes } from "react-router-dom";
import { ProtectedLoginRoute } from "./components/authLoginGuard";
import AdminPage from "./pages/AdminPage";
import LoginAdminPage from "./pages/AdminPage/LoginPage";
import CommunityPage from "./pages/CommunityPage";
import FlowPage from "./pages/FlowPage";
import HomePage from "./pages/MainPage";
import DeleteAccountPage from "./pages/deleteAccountPage";
import LoginPage from "./pages/loginPage";
import SignUp from "./pages/signUpPage";
import { CatchAllRoute } from "./components/catchAllRoutes";
import { ProtectedRoute } from "./components/authGuard";
import { ProtectedAdminRoute } from "./components/authAdminGuard";

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
      />
      <Route
        path="/community"
        element={
          <ProtectedRoute>
            <CommunityPage />
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
  );
};

export default Router;
