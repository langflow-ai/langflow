import { useState } from "react";
import { gradients } from "../../utils/styleUtils";


export default function GradientChooserComponent({value, onChange}){
    return (
        <div className="flex flex-wrap gap-4 justify-center items-center">
            {gradients.map((gradient, idx) => 
            <div onClick={() => {onChange(gradient)}} className={"w-12 h-12 rounded-full transition-all duration-400 " + gradient + (value === gradient ?  " shadow-lg ring-2 ring-primary" : "")} key={idx}></div>
            )}
            </div>
    )
}