import 'reactflow/dist/style.css';
import { useState, useCallback } from 'react';
import ReactFlow, { addEdge, applyEdgeChanges, applyNodeChanges, Background, Controls, Position } from 'reactflow';
import type { Node, Edge } from 'reactflow';
import TextUpdaterNode from '../CustomNodes/inputTextFolder';
import '../CustomNodes/inputTextFolder/inputText.css'
import PromptNode from '../CustomNodes/PromptNode';
import { prompt } from '../data_assets/prompt';
    // outside component to avoid render trigger
    const nodeTypes = {textUpdater:TextUpdaterNode, promptNode:PromptNode}

    const rfStyle={
        backgroundCOlor:"#B8CEFF"
    }

export default function Flow(){
    

    const [nodes,setNodes] =  useState<Array<Node>>([{id:'1', position:{x:0,y:0}, data:{label:"node"},style:{color:"blue", width:100, height:40},sourcePosition:Position.Left,targetPosition:Position.Right},
    {id:'2',data:{label:"world"},position:{x:100,y:100}}, {id:'4',data:prompt,position:{x:50,y:120},type:"promptNode"}])
    const [edges,setEdges] = useState<Array<Edge>>([])
    //allow iteractive with the react flow
    const onNodesChange = useCallback( (changes) => setNodes((nds) => applyNodeChanges(changes, nds)),[] );
    const onEdgesChange = useCallback( (changes) => setEdges((eds) => applyEdgeChanges(changes, eds)),[] );
    const onConnect = useCallback((params)=>setEdges((eds)=>addEdge(params,eds)),[])

    return (
        //need parent component with width and height
        <div className='w-full h-full'>
            <ReactFlow 
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect = {onConnect}
            nodeTypes={nodeTypes}
            fitView
            >
                <Background/>
                    <Controls></Controls>
            </ReactFlow>
        </div>
    )
}