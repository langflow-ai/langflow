import {
  ArrowUpRightIcon,
  TrashIcon,
  PlayIcon,
} from "@heroicons/react/24/outline";
import { Handle, Position } from "reactflow";
import Dropdown from "../../components/dropdownComponent";
import Input from "../../components/inputComponent";
import {
  isValidConnection,
  nodeColors,
  nodeIcons,
  snakeToNormalCase,
} from "../../utils";
import Tooltip from "../../components/TooltipComponent";
import { useEffect, useRef, useState } from "react";
import ParameterComponent from "./components/parameterComponent";

export default function GenericNode({ data }) {
  const Icon = nodeIcons[data.type];

  return (
    <div className="prompt-node relative bg-white w-96 rounded-lg solid border flex flex-col justify-center">
      <div className="w-full flex items-center justify-between p-4 gap-8 bg-gray-50 border-b ">
        <div className="w-full flex items-center truncate gap-4 text-lg">
          <Icon
            className="w-10 h-10 p-1 text-white rounded"
            style={{ background: nodeColors[data.type] }}
          />
          <div className="truncate">{data.name}</div>
        </div>
        <button onClick={data.onDelete}>
          <TrashIcon className="w-6 h-6 hover:text-red-500"></TrashIcon>
        </button>
      </div>

      <div className="w-full h-full py-5 pointer-events-none">
        <div className="w-full text-gray-500 px-5 text-sm">
          {data.node.description}
        </div>

        <>
          {Object.keys(data.node.template)
            .filter((t) => t.charAt(0) !== "_")
            .map((t, idx) => (
              <>
                {idx === 0 ? (
                  <div className="px-5 py-2 mt-2 text-center">Inputs:</div>
                ) : (
                  <></>
                )}
                {data.node.template[t].show ? (
                  <ParameterComponent
                    key={idx}
                    data={data}
                    color={
                      nodeColors[data.types[data.node.template[t].type]] ??
                      "black"
                    }
                    title={
                      snakeToNormalCase(t) +
                      (data.node.template[t].required ? " (required)" : "")
                    }
                    tooltipTitle={
                      "Type: " +
                      data.node.template[t].type +
                      (data.node.template[t].list ? " list" : "") +
                      (data.node.template[t].required ? " (required)" : "")
                    }
                    id={data.node.template[t].type + "|" + t + "|" + data.id}
                    left={true}
                  />
                ) : (
                  <></>
                )}
              </>
            ))}
          <div className="px-5 py-2 mt-2 text-center">Output:</div>
          <ParameterComponent
            data={data}
            color={nodeColors[data.type]}
            title={data.name + " | " + data.node.base_class}
            tooltipTitle={"Type: str"}
            id={data.name + "|" + data.node.base_class + "|" + data.id}
            left={false}
          />
        </>
      </div>
    </div>
  );
}
