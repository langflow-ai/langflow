import 'reactflow/dist/style.css';
import { useState, useCallback } from 'react';
import ReactFlow, { addEdge, applyEdgeChanges, applyNodeChanges, Background, Controls } from 'reactflow';
import type { Node, Edge } from 'reactflow';
import TextUpdaterNode from '../CustomNodes/inputTextFolder';
import '../CustomNodes/inputTextFolder/inputText.css'
import { type } from 'os';

    // outside component to avoid render trigger
    const nodeTypes = {textUpdater:TextUpdaterNode}

    const rfStyle={
        backgroundCOlor:"#B8CEFF"
    }

export default function Flow(){
    

    const [nodes,setNodes] =  useState<Array<Node>>([{id:'1', position:{x:0,y:0}, data:{label:"hello"}},
    {id:'2',data:{label:"world"},position:{x:100,y:100}}, {id:'text-node1',position:{x:50,y:50},data:{value:123}, type:"textUpdater"}])
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