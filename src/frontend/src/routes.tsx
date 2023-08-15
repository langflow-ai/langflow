import { Route, Routes } from "react-router-dom";
import CommunityPage from "./pages/CommunityPage";
import FlowPage from "./pages/FlowPage";
import HomePage from "./pages/MainPage";
import ViewPage from "./pages/ViewPage";

const Router = () => {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/community" element={<CommunityPage />} />
      <Route path="/flow/:id/">
        <Route path="" element={<FlowPage />} />
        <Route path="view" element={<ViewPage />} />
      </Route>
      <Route path="*" element={<HomePage />} />
    </Routes>
  );
};

export default Router;
