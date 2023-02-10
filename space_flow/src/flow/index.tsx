import 'reactflow/dist/style.css';
import { useState, useCallback, useRef } from 'react';
import ReactFlow, { addEdge, applyEdgeChanges, applyNodeChanges, Background, Controls, Position, useNodesState, useEdgesState, ReactFlowProvider } from 'reactflow';
import type { Node, Edge } from 'reactflow';
import TextUpdaterNode from '../CustomNodes/inputTextFolder';
import '../CustomNodes/inputTextFolder/inputText.css'
import PromptNode from '../CustomNodes/PromptNode';
import { prompt } from '../data_assets/prompt';
import { Sidebar } from '../components/sidebar';
import ModelNode from '../CustomNodes/ModelNode';
    // outside component to avoid render trigger
    const nodeTypes = {textUpdater:TextUpdaterNode, promptNode:PromptNode,modelNode:ModelNode}

    const rfStyle={
        backgroundCOlor:"#B8CEFF"
    }
    let id = 0;
    const getId = () => `dndnode_${id++}`;

export default function Flow(){
    
    const reactFlowWrapper = useRef(null)
    const [nodes,setNodes,onNodesChange] =  useNodesState([])
    const [edges,setEdges, onEdgesChange] = useEdgesState([])
    const [reactFlowInstance,setReactFlowInstance] = useState(null)
    const onConnect = useCallback((params)=>setEdges((eds)=>addEdge(params,eds)),[])
    const onDragOver = useCallback((event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
      }, []);
    const onDrop = useCallback(
        (event)=>{
            event.preventDefault();
        
            const reactflowBounds = reactFlowWrapper.current.getBoundingClientRect();
            const type = event.dataTransfer.getData('application/reactflow');
            let data = JSON.parse(event.dataTransfer.getData('json'))
            // check if the dropped element is valid
            if (typeof type === 'undefined' || !type) {
              return;
            }

            const position = reactFlowInstance.project({x:event.clientX-reactflowBounds.top, y:event.clientY - reactflowBounds.top})
            const newNode = {
                id:getId(),
                type,
                position,
                data:{...data,delete:()=>console.log("asdsdsadad")}
            }
            setNodes((nds)=>nds.concat(newNode))



        },[reactFlowInstance])

    return (
        //need parent component with width and height
        <div className='w-full h-full flex flex-row'>
            <ReactFlowProvider>
            <Sidebar/>
            <div className='w-screen h-full' ref={reactFlowWrapper}>
            <ReactFlow 
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect = {onConnect}
            onInit={setReactFlowInstance}
            nodeTypes={nodeTypes}
            onDragOver={onDragOver}
            onDrop={onDrop}
            fitView
            >
                <Background/>
                    <Controls></Controls>
            </ReactFlow>
            </div>
            </ReactFlowProvider>
        </div>
    )
}