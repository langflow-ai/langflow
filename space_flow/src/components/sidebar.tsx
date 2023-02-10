import { prompt } from "../data_assets/prompt";
import { llm_chain } from "../data_assets/llm_chain";

export function Sidebar(){

    function onDragStart(event:React.DragEvent<any>,nodeType){
        let json;
        event.dataTransfer.setData('application/reactflow',nodeType)
        event.dataTransfer.effectAllowed = 'move'
        if(nodeType==="promptNode"){
            json = JSON.stringify(prompt)
        }
        if(nodeType==="modelNode"){
            json = JSON.stringify(llm_chain)
        }
        event.dataTransfer.setData('json',json);
    }

    return(
    <div className="h-full w-48 bg-slate-200 flex flex-col">
        <div className="w-full text-center border border-black cursor-grab" onDragStart={(event)=>onDragStart(event,'promptNode')}> prompt Node</div>
        <div className="w-full text-center border border-black cursor-grab" onDragStart={(event)=>onDragStart(event,'modelNode')}> Model Node</div>
    </div>
    )
}