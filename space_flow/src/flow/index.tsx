import 'reactflow/dist/style.css';
import ReactFlow, { Background, Controls } from 'reactflow';


export default function Flow(){
    return (
        //need parent component with width and height
        <div className='w-full h-full'>
            <ReactFlow>
                <Background/>
                    <Controls></Controls>
            </ReactFlow>
        </div>
    )
}