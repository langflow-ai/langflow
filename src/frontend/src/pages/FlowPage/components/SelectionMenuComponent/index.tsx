import { Dialog } from "@headlessui/react";
import { useRef } from "react";

export default function SelectionMenu({onClick, position, isVisible, setIsVisible}){
    const dialogRef = useRef(null);
    return (
        <Dialog
				as="div"
				className="absolute z-50" style={{left: position.x, top: position.y}}
                open={isVisible}
				onClose={setIsVisible}
                initialFocus={dialogRef}
			>
                <Dialog.Panel as="div" ref={dialogRef} className="bg-red-500 text-white w-24 h-8 text-center">
                <button type="button" onClick={onClick}>
                    <div className="">teste</div>
                </button>
                </Dialog.Panel>


            </Dialog>
    )
}
    

