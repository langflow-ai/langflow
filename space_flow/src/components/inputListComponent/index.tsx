import { useState } from "react";

var _ = require('lodash');

export default function InputListComponent({value, onChange}){
    const [inputList, setInputList] = useState(value ?? []);

    return (
        <>
            {inputList.map((i, idx) =>(
                <input
                type="text"
                value={i}
                className="block w-full form-input rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                placeholder="Type a text"
                onChange={(e) => {
                    setInputList((old) => {
                        let newInputList = _.cloneDeep(old);
                        newInputList[idx] = e.target.value;
                        return newInputList;
                    });
                    onChange(inputList);
                }}
                />
            ))}
            
        </>
    );
}