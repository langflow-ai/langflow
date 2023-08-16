import { Route, Routes } from "react-router-dom";
import AdminPage from "./pages/AdminPage";
import LoginAdminPage from "./pages/AdminPage/LoginPage";
import CommunityPage from "./pages/CommunityPage";
import FlowPage from "./pages/FlowPage";
import HomePage from "./pages/MainPage";
import DeleteAccountPage from "./pages/deleteAccountPage";
import LoginPage from "./pages/loginPage";

const Router = () => {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/community" element={<CommunityPage />} />
      <Route path="/flow/:id/">
        <Route path="" element={<FlowPage />} />
      </Route>
      <Route path="*" element={<HomePage />} />

      <Route path="/login" element={<LoginPage />} />
      {/* <Route path="/signup" element={<SignUp />} /> */}
      <Route path="/login/admin" element={<LoginAdminPage />} />

      <Route path="/admin" element={<AdminPage />} />

      <Route path="/account">
        <Route path="delete" element={<DeleteAccountPage />}></Route>
      </Route>
    </Routes>
  );
};

export default Router;
