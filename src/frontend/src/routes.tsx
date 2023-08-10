import { Route, Routes } from "react-router-dom";
import CommunityPage from "./pages/CommunityPage";
import FlowPage from "./pages/FlowPage";
import FormPage from "./pages/FormPage";
import HomePage from "./pages/MainPage";

const Router = () => {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/community" element={<CommunityPage />} />
      <Route path="/flow/:id/">
        <Route path="" element={<FlowPage />} />
      </Route>
      <Route path="/form/:id/">
        <Route path="" element={<FormPage />} />
      </Route>
      <Route path="*" element={<HomePage />} />
    </Routes>
  );
};

export default Router;
