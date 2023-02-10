import { classNames } from "../../../utils"
import { Link } from "react-router-dom"
import { useContext } from "react"
import { locationContext } from "../../../contexts/locationContext";

export default function SidebarButton({item}){
    let {atual}= useContext(locationContext);
    return (
        <>
        <Link
        key={item.name}
        to={item.href}
        className={classNames(
            item.href.split("/")[1]=== atual[3]? 'bg-gray-900 text-white' : 'text-gray-400 hover:bg-gray-700',
            'flex-shrink-0 inline-flex items-center justify-center h-14 w-14 rounded-lg'
        )}
        >
        <span className="sr-only">{item.name}</span>
        <item.icon className="h-6 w-6" aria-hidden="true" />
        </Link>
        </>
    )
}