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
import { useEffect } from "react";

// uncomment if you need to run this independently
// const container = document.getElementById("root");
// if (container) {
//   const root = ReactDOM.createRoot(container);
//   root.render(
//       <App />
//   );
// }

// export default App;

const LangflowApp = () => {
  useEffect(() => {
    console.log("Langflow App mounted");
  }, []);
  return (
    <>
      <h1>Langflow</h1>
      {/* <button onClick={() => alert("Working!")}>Test Button</button> */}
      <App />
    </>
  );
};

export default LangflowApp;
