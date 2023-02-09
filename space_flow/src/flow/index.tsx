import 'reactflow/dist/style.css';
import { useState, useCallback, useRef } from 'react';
import ReactFlow, { addEdge, applyEdgeChanges, applyNodeChanges, Background, Controls, Position, useNodesState, useEdgesState, ReactFlowProvider } from 'reactflow';
import type { Node, Edge } from 'reactflow';
import TextUpdaterNode from '../CustomNodes/inputTextFolder';
import '../CustomNodes/inputTextFolder/inputText.css'
import PromptNode from '../CustomNodes/PromptNode';
import { prompt } from '../data_assets/prompt';
import { Sidebar } from '../components/sidebar';
    // outside component to avoid render trigger
    const nodeTypes = {textUpdater:TextUpdaterNode, promptNode:PromptNode}

    const rfStyle={
        backgroundCOlor:"#B8CEFF"
    }
    let id = 0;
    const getId = () => `dndnode_${id++}`;

export default function Flow(){
    
    const reactFlowWrapper = useRef(null)
    const [nodes,setNodes,onNodesChange] =  useNodesState([])
    const [edges,setEdges, onEdgesChange] = useEdgesState([])
    //allow iteractive with the react flow
    // const onNodesChange = useCallback( (changes) => setNodes((nds) => applyNodeChanges(changes, nds)),[] );
    // const onEdgesChange = useCallback( (changes) => setEdges((eds) => applyEdgeChanges(changes, eds)),[] );
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
            let json = JSON.parse(event.dataTransfer.getData('json'))
            const data = {...json}
            data.onClick = console.log("clicked")
            // check if the dropped element is valid
            if (typeof type === 'undefined' || !type) {
              return;
            }

            const position = reactFlowInstance.project({x:event.clientX-reactflowBounds.top, y:event.clientY - reactflowBounds.top})
            const newNode = {
                id:getId(),
                type,
                position,
                data
            }
            setNodes((nds)=>nds.concat(newNode))



        },[reactFlowInstance])

    return (
        //need parent component with width and height
        <div className='w-full h-full'>
            <ReactFlowProvider>
            <Sidebar/>
            <div className='w-full h-full' ref={reactFlowWrapper}>
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