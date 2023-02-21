import { XMarkIcon } from "@heroicons/react/24/solid";
import { classNames } from "../../../../utils";

type tabProps = {
    name:string;
}


export default function TabComponent({children,selected}){
    return(
        <div className={classNames(selected?" shadow-lg":"bg-gray-300","flex border-t border-l border-r border-black rounded-t-md shadow-sm cursor-pointer")}>
            {children}
            <XMarkIcon className="w-5 hover:text-red-500"></XMarkIcon>
        </div>
    )
}