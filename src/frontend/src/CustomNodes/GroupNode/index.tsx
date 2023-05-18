import { useContext, useState } from "react";
import { FlowType } from "../../types/flow";
import { classNames, concatFlows, expandGroupNode, isValidConnection, nodeColors, nodeIcons, updateFlowPosition } from "../../utils";
import { typesContext } from "../../contexts/typesContext";
import { Handle, Position } from "reactflow";
import Tooltip from "../../components/TooltipComponent";
import FlowHandle from "./components/flowHandle";
import {XYPosition} from "reactflow"
import { ArrowsPointingOutIcon, TrashIcon } from "@heroicons/react/24/outline";

export default function GroupNode({ data, selected,xPos,yPos  }: { data: FlowType, selected: boolean,xPos:number,yPos:number  }) {
    const [isValid, setIsValid] = useState(true);
    const { reactFlowInstance, deleteNode } = useContext(typesContext);
    const Icon = nodeIcons['custom'];
    return (
        <div
            className={classNames(
                isValid ? "animate-pulse-green" : "border-red-outline",
                selected ? "border border-blue-500" : "border dark:border-gray-700",
                "prompt-node relative bg-white dark:bg-gray-900 w-96 rounded-lg flex flex-col justify-center"
            )}
        >
            <div className="w-full dark:text-white flex items-center justify-between p-4 gap-8 bg-gray-50 rounded-t-lg dark:bg-gray-800 border-b dark:border-b-gray-700 ">
                <div className="w-full flex items-center truncate gap-2 text-lg">
                    <Icon
                        className="w-10 h-10 p-1 rounded"
                        style={{
                            color: nodeColors['custom'] ?? nodeColors.unknown,
                        }}
                    />
                    <div className="ml-2 truncate">{data.name}</div>
                    <div>
                        {/* <div className="relative w-5 h-5">
                    <CheckCircleIcon
                      className={classNames(
                        validationStatus && validationStatus.valid ? "text-green-500 opacity-100" : "text-red-500 opacity-0",
                        "absolute w-5 hover:text-gray-500 hover:dark:text-gray-300 transition-all ease-in-out duration-300"
                      )}
                    />
                    <ExclamationCircleIcon
                      className={classNames(
                        validationStatus && !validationStatus.valid ? "text-red-500 opacity-100" : "text-red-500 opacity-0",
                        "w-5 absolute hover:text-gray-500 hover:dark:text-gray-600 transition-all ease-in-out duration-300"
                      )}
                    />
                    <EllipsisHorizontalCircleIcon
                      className={classNames(
                        !validationStatus ? "text-yellow-500 opacity-100" : "text-red-500 opacity-0",
                        "w-5 absolute hover:text-gray-500 hover:dark:text-gray-600 transition-all ease-in-out duration-300"
                      )}
                    />
                  </div> */}
                    </div>
                </div>
                <div className="flex gap-3">
                    <button
                        onClick={() => { 
                            updateFlowPosition({x:xPos,y:yPos},data)
                            expandGroupNode(data,reactFlowInstance)
                        }}>
                        <ArrowsPointingOutIcon className="w-6 h-6 hover:text-blue-500 dark:text-gray-300 dark:hover:text-blue-500" />
                    </button>
                    <button
                        onClick={() => {
                            console.log(data.id);
                            deleteNode(data.id);
                        }}
                    >
                        <TrashIcon className="w-6 h-6 hover:text-red-500 dark:text-gray-300 dark:hover:text-red-500"></TrashIcon>
                    </button>
                </div>
            </div>
            <div className="w-full h-full py-5">
                <div className="w-full text-gray-500 dark:text-gray-300 px-5 pb-3 text-sm">
                    {data.description?.length > 0 ? data.description : "No description"}
                </div>
                <>
                    <FlowHandle
                        left={true}
                        data={data}
                        required={true}
                        title="Input"
                        tooltipTitle="Type: Text"
                        color={nodeColors['custom']}
                        id={['Text', 'output_connection', data.id].join("|")}
                    />
                    <FlowHandle
                        left={false}
                        data={data}
                        required={true}
                        title="Input"
                        tooltipTitle="Type: Text"
                        color={nodeColors['custom']}
                        id={['Text', data.id, 'output_connection'].join("|")}
                    />

                    {/* <ParameterComponent
                        data={data}
                        color={nodeColors[types[data.type]] ?? nodeColors.unknown}
                        title={data.type}
                        tooltipTitle={`Type: ${data.node.base_classes.join(" | ")}`}
                        id={[data.type, data.id, ...data.node.base_classes].join("|")}
                        type={data.node.base_classes.join("|")}
                        left={false}
                    /> */}
                </>
            </div>
        </div>
    );
}