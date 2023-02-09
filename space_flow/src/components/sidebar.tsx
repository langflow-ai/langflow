import { prompt } from "../data_assets/prompt";

export function Sidebar(){

    function onDragStart(event:React.DragEvent<any>,nodeType){
        event.dataTransfer.setData('application/reactflow',nodeType)
        event.dataTransfer.effectAllowed = 'move'
        event.dataTransfer.setData('json',JSON.stringify(prompt));
    }

    return(
    <div className="h-full w-48 bg-slate-200 absolute z-10 flex flex-col">
        <div className="w-full text-center border border-black cursor-grab" onDragStart={(event)=>onDragStart(event,'promptNode')}> prompt Node</div>
    </div>
    )
}