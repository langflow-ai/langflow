import { useContext } from "react";
import { IOViewType } from "../../types/components";
import { flowManagerContext } from "../../contexts/flowManagerContext";
import TextInputComponent from "../textInputComponent";
import TextOutputComponent from "../textOutputComponent";

export default function IOView({ inputNodeIds, outputNodeIds }: IOViewType): JSX.Element {
    const { flowPool } = useContext(flowManagerContext)
    return (
        <div className="flex w-full justify-around">
            <div className="flex flex-col gap-4">
                <strong>
                    Inputs:
                </strong>
                {inputNodeIds.map((inputType,index) => {
                    const params = flowPool[inputType]?.params as string
                    return (<div key={index}>
                        <TextInputComponent text={params} emissor={inputType}></TextInputComponent>
                    </div>)
                })}
            </div>
            <div className="flex flex-col gap-4">
                <strong>
                    Outputs:
                </strong>
                {outputNodeIds.map((outputType,index) => {
                    const text = flowPool[outputType]?.results?.result as string

                    return (<div key={index}>
                        <TextOutputComponent text={text} emissor={outputType}></TextOutputComponent>
                    </div>)
                })}
            </div>

        </div>
    )
}