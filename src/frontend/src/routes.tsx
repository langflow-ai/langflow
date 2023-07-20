import { Route, Routes } from "react-router-dom";
import HomePage from "./pages/MainPage";
import FlowPage from "./pages/FlowPage";
import TemplatesPage from "./pages/TemplatesPage";

const Router = () => {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/templates" element={<TemplatesPage />} />
      <Route path="/flow/:id/">
        <Route path="" element={<FlowPage />} />
      </Route>
      <Route path="*" element={<HomePage />} />
    </Routes>
  );
};

export default Router;
