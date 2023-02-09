import Flow from "./flow";
import "./App.css";
import { Sidebar } from "./components/sidebar";
function App() {
  return (
    <div className="w-screen h-screen">
      <Sidebar/>
      <Flow></Flow> 
    </div>
  );
}

export default App;
