import ForwardedIconComponent from "@/components/genericIconComponent"
import { IS_MAC } from "@/constants/constants"

export default function RenderKey({value}: {value: string}): JSX.Element {
    const check = value.toLowerCase().trim()
    return (
        <div>
            {check === "shift" ? (
                <ForwardedIconComponent name="ArrowBigUp" className="h-4 w-4" />
            ) : check === "ctrl" && IS_MAC  ? (
                <span className="text-xs">⌃</span>
            ) : check === "alt" && IS_MAC ? (
                <ForwardedIconComponent name="OptionIcon" className="h-3 w-3" />
            ) : check === "cmd" ? (
                <ForwardedIconComponent name="Command" className="h-3 w-3" />
            ) : (
                <span className="text-xs">{value}</span>
            )}
        </div>
    )
}
