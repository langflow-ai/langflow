import { useState } from "react";

export default function TipComponent({ param }) {

    const [enable, setEnable] = useState(!param.advanced)

    return (
        <div className="items-center text-center">
            {/* <ToggleShadComponent
                enabled={enable}
                setEnabled={(e) =>{
                    param.advanced = !param.advanced
                    setEnable(old=>!old)
                }
                }
                disabled={false}
                size="small"
            /> */}
        </div>
    )
}