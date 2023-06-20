import { useState } from "react";
import ToggleShadComponent from "../../../components/toggleShadComponent";

export default function AdvancedToogle({ param }) {
    const [enable, setEnable] = useState(!param.advanced)
    return (
        <div className="items-center text-center">
            <ToggleShadComponent
                enabled={enable}
                setEnabled={(e) =>{
                    param.advanced = !param.advanced
                    setEnable(old=>!old)
                }
                }
                disabled={false}
                size="small"
            />
        </div>
    )
}