import Flow from "./flow";
import "./App.css";
import PopUpProvider from "./context/popUpContext";
function App() {
  return (
    <PopUpProvider>
      <div className="w-screen h-screen">
        <Flow></Flow>
      </div>
    </PopUpProvider>
  );
}

export default App;
