import { useState } from "react";

export default function Input({value, onChange}){
    const [myValue, setMyValue] = useState(value ?? "");
    return (
        <>
            <input
            type="text"
            value={myValue}
            className="block w-full form-input rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            placeholder="Type a text"
            onChange={(e) => {
                setMyValue(e.target.value);
                onChange(e.target.value);
            }}
            />
        </>
    );
}