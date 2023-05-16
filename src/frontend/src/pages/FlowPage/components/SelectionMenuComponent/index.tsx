import { Dialog } from "@headlessui/react";
import { useEffect, useRef } from "react";

export default function SelectionMenu({onClick, position, isVisible, setIsVisible}){
    const menuRef = useRef(null);
    // Event listener to detect clicks outside the div
  const handleDocumentClick = (event) => {
    if (menuRef.current && !menuRef.current.contains(event.target)) {
      setIsVisible(false);
      console.log("kkk")
    }
  };

  // Add the event listener in a useEffect hook
  useEffect(() => {
    if(menuRef){
        document.addEventListener('mousedown', handleDocumentClick);

        // Clean up the event listener on component unmount
        return () => {
          document.removeEventListener('mousedown', handleDocumentClick);
        };
    }
    
  }, [menuRef]);

    
    return (
        <Dialog
				as="div"
				className="absolute text-center bg-red-500 z-50 w-24 h-8" style={{left: position.x, top: position.y}}
                open={isVisible}
				onClose={setIsVisible}
			>
                <button onClick={onClick}>
                teste
            </button>


            </Dialog>
    )
}
    

