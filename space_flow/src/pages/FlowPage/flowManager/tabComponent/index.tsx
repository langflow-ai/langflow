type tabProps = {
    name:string;
}


export default function TabComponent({children}){
    return(
        <div className="bg-blue-400 w-2">
            {children}
        </div>
    )
}