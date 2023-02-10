import { llm_chain } from "../../../../data_assets/llm_chain";
import { prompt } from "../../../../data_assets/prompt";


export function ExtraSidebar(){

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
        if(nodeType==="chainNode"){
            json = JSON.stringify({content:""})
        }
        if(nodeType==="agentNode"){
            json = JSON.stringify({content:""})
        }
        if(nodeType==="validatorNode"){
            json = JSON.stringify({content:""})
        }
        event.dataTransfer.setData('json',json);
    }

    return(
    <div className="h-full w-48 bg-slate-200 flex flex-col">
        <div draggable className="w-full text-center border border-black cursor-grab" onDragStart={(event)=>onDragStart(event,'promptNode')}> Prompt Node</div>
        <div draggable className="w-full text-center border border-black cursor-grab" onDragStart={(event)=>onDragStart(event,'modelNode')}> Model Node</div>
        <div draggable className="w-full text-center border border-black cursor-grab" onDragStart={(event)=>onDragStart(event,'chainNode')}> Chain Node</div>
        <div draggable className="w-full text-center border border-black cursor-grab" onDragStart={(event)=>onDragStart(event,'agentNode')}> Agent Node</div>
        <div draggable className="w-full text-center border border-black cursor-grab" onDragStart={(event)=>onDragStart(event,'validatorNode')}> Validator Node</div>

    </div>
    )
}