import {
  TrashIcon,
} from "@heroicons/react/24/outline";
import {
  classNames,
  nodeColors,
  nodeIcons,
  snakeToNormalCase,
} from "../../utils";
import ParameterComponent from "./components/parameterComponent";
import { typesContext } from "../../contexts/typesContext";
import { useContext } from "react";
import { NodeDataType} from "../../types/flow";

export default function GenericNode({ data, selected}:{data:NodeDataType,selected:boolean}) {
  const {types, deleteNode} = useContext(typesContext);
  const Icon = nodeIcons[types[data.type]];


  return (
    <div className={ classNames(selected?"border border-blue-500":"border dark:border-gray-700","prompt-node relative bg-white dark:bg-gray-900 w-96 rounded-lg flex flex-col justify-center")}>
      <div className="w-full dark:text-white flex items-center justify-between p-4 gap-8 bg-gray-50 rounded-t-lg dark:bg-gray-800 border-b dark:border-b-gray-700 ">
        <div className="w-full flex items-center truncate gap-4 text-lg">
          <Icon
            className="w-10 h-10 p-1 rounded"
            style={{ color: nodeColors[types[data.type]] }}
          />
          <div className="truncate">{data.type}</div>
        </div>
        <button onClick={() => {deleteNode(data.id)}}>
          <TrashIcon className="w-6 h-6 hover:text-red-500 dark:text-gray-500 dark:hover:text-red-500"></TrashIcon>
        </button>
      </div>

      <div className="w-full h-full py-5">
        <div className="w-full text-gray-500 px-5 text-sm">
          {data.node.description}
        </div>

        <>
          {Object.keys(data.node.template)
            .filter((t) => t.charAt(0) !== "_")
            .map((t:string, idx) => (
              <div key={idx}>
                {idx === 0 ? (
                  <div className="px-5 py-2 mt-2 dark:text-white text-center">Inputs:</div>
                ) : (
                  <></>
                )}
                {data.node.template[t].show ? (
                  <ParameterComponent
                    
                    data={data}
                    color={
                      nodeColors[types[data.node.template[t].type]] ??
                      nodeColors[types[data.node.template[t].type]] ??
                      "black"
                    }
                    title={
                      snakeToNormalCase(t)
                    }
                    name={t}
                    tooltipTitle={
                      "Type: " +
                      data.node.template[t].type +
                      (data.node.template[t].list ? " list" : "")
                    }
                    required={data.node.template[t].required}
                    id={data.node.template[t].type + "|" + t + "|" + data.id}
                    left={true}
                    type={data.node.template[t].type}
                  />
                ) : (
                  <></>
                )}
              </div>
            ))}
          <div className="px-5 py-2 mt-2 dark:text-white text-center">Output:</div>
          <ParameterComponent
            data={data}
            color={nodeColors[types[data.type]]}
            title={data.type}
            tooltipTitle={"Type: str"}
            id={data.type + "|" + data.id + data.node.base_classes.map((b) => ("|" + b))}
            type={'str'}
            left={false}
          />
        </>
      </div>
    </div>
  );
}
