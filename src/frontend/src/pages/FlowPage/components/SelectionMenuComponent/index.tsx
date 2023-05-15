export default function SelectionMenu({onClick, position, isVisible}){
    return (
        <div className={"absolute text-center bg-red-500 z-50 w-24 -ml-12 h-8 -mt-8 " + (isVisible ? "" : "hidden")} style={{left: position.x, top: position.y}}>
            <button onClick={onClick}>
                teste
            </button>
        </div>
    )
}
    

