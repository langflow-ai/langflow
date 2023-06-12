import { Route, Routes } from "react-router-dom"
import HomePage from "./pages/MainPage";
import FlowPage from "./pages/FlowPage";

const Router = () => {
    return(
         <Routes>
             <Route path="/" element={<HomePage/>}/>
             <Route path="/flow/:id/">
                <Route path="" element={<FlowPage/>}/>
            </Route>
        </Routes>
    )
 }
 
 export default Router;