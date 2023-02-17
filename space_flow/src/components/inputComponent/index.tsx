import { useEffect, useState } from "react";

export default function InputComponent({value, onChange, disabled}){
    const [myValue, setMyValue] = useState(value ?? "");
    useEffect(()=> {
        if(disabled){
            setMyValue("");
            onChange("");
        }
    }, [disabled, onChange])
    return (
        <div className={disabled ? "pointer-events-none cursor-not-allowed" : ""}>
            <input
            type="text"
            value={myValue}
            className={"block w-full form-input rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm" + (disabled ? " bg-gray-200" : "")}
            placeholder="Type a text"
            onChange={(e) => {
                setMyValue(e.target.value);
                onChange(e.target.value);
            }}
            />
        </div>
    );
}