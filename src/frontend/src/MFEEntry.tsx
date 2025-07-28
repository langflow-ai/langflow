// frontend/src/MFEEntry.tsx
import React from "react";
import ReactDOM from "react-dom/client";

// Import all the styles that are needed
import "@xyflow/react/dist/style.css";
import "./style/classes.css";
import "./style/index.css";
import "./App.css";
import "./style/applies.css";

import App from "./App";

const container = document.getElementById("root");
if (container) {
  const root = ReactDOM.createRoot(container);
  root.render(
      <App />
  );
}

export default App;
