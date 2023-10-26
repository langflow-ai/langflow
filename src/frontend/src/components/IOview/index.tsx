import { IOViewType } from "../../types/components";

export default function IOView({ children,inputTypes,outputTypes }:IOViewType): JSX.Element {
    return (
        <div>
            {children}
        </div>
    )
}