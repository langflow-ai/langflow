import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import ContextWrapper from "./contexts";
import reportWebVitals from "./reportWebVitals";

import "./index.css";
import { ToastContainer } from "react-toastify";

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement
);
root.render(
  <ContextWrapper>
    <BrowserRouter>
      <App />
      <ToastContainer
position="bottom-left"
autoClose={3000}
limit={1}
hideProgressBar={false}
newestOnTop={false}
closeOnClick
rtl={false}
pauseOnFocusLoss
draggable
pauseOnHover
theme="colored"
/>
    </BrowserRouter>
  </ContextWrapper>
);
reportWebVitals();
