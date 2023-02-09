import { useCallback } from 'react';
import { Handle, Position } from 'reactflow';


const handleStyle = {left:10};

export default function TextUpdaterNode({data}) 
{
    const onChange = useCallback((evt)=>{
        console.log(evt.target.value)
    },[])


    return (
        <div className="text-updater-node">
            <Handle type='target' position={Position.Top}/>
            <div>
                <label htmlFor='text'>Text:</label>
                <input id="text" name="text" onChange={onChange}></input>
            </div>
            <Handle type='source' id='a' position={Position.Bottom} style={handleStyle}/>
            <Handle type='source' id='b' position={Position.Bottom}/>
        </div>
    )
}



