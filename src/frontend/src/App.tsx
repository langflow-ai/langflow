import { Suspense } from "react";
import { RouterProvider } from "react-router-dom";
import "reactflow/dist/style.css";
import { LoadingPage } from "./pages/LoadingPage";
import router from "./routes";

export default function App() {
  return (
    <Suspense fallback={<LoadingPage />}>
      <RouterProvider router={router} />
    </Suspense>
  );
}
