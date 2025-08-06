// frontend/src/MFEEntry.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Import all the styles that are needed
import "@xyflow/react/dist/style.css";
import "./style/classes.css";
import "./style/index.css";
import "./App.css";
import "./style/applies.css";

import App from "./App";
import { useEffect } from "react";
import { useFolderStore } from "./stores/foldersStore";

// uncomment if you need to run this independently
// const container = document.getElementById("root");
// if (container) {
//   const root = ReactDOM.createRoot(container);
//   root.render(
//       <App />
//   );
// }

// export default App;
const queryClient = new QueryClient();

const LangflowApp = () => {
  useEffect(() => {
    console.log("Langflow App mounted");
    // useFolderStore.setState({
    //   myCollectionId: "eafeef52-0a76-4b6a-b707-a63cbf1178db",
    // });
  }, []);
  return (
    <>
      {/* <QueryClientProvider client={queryClient}> */}
      {/* <ErrorBoundary> */}
      {/* <h1>Langflow</h1> */}
      {/* <button onClick={() => alert("Working!")}>Test Button</button> */}
      <App />
      {/* </ErrorBoundary> */}
      {/* </QueryClientProvider> */}
    </>
  );
};

export default LangflowApp;
