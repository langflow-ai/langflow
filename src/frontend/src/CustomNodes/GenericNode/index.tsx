import {
  BugAntIcon,
  Cog6ToothIcon,
  InformationCircleIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";

import {
  CheckCircleIcon,
  EllipsisHorizontalCircleIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/24/solid";

import {
  classNames,
  nodeColors,
  nodeIcons,
  toNormalCase,
  toTitleCase,
} from "../../utils";
import ParameterComponent from "./components/parameterComponent";
import { typesContext } from "../../contexts/typesContext";
import { useContext, useState, useEffect, useRef, Fragment } from "react";
import { NodeDataType } from "../../types/flow";
import { alertContext } from "../../contexts/alertContext";
import { PopUpContext } from "../../contexts/popUpContext";
import NodeModal from "../../modals/NodeModal";
import { useCallback } from "react";
import { TabsContext } from "../../contexts/tabsContext";
import { debounce } from "../../utils";
import Tooltip from "../../components/TooltipComponent";
import ShadTooltip from "../../components/ShadTooltipComponent";
export default function GenericNode({
  data,
  selected,
}: {
  data: NodeDataType;
  selected: boolean;
}) {
  const { setErrorData } = useContext(alertContext);
  const showError = useRef(true);
  const { types, deleteNode } = useContext(typesContext);
  const { openPopUp } = useContext(PopUpContext);

  const Icon = nodeIcons[data.type] || nodeIcons[types[data.type]];
  const [validationStatus, setValidationStatus] = useState(null);
  // State for outline color
  const [isValid, setIsValid] = useState(false);
  const { save } = useContext(TabsContext);
  const { reactFlowInstance } = useContext(typesContext);
  const [params, setParams] = useState([]);

  useEffect(() => {
    if (reactFlowInstance) {
      setParams(Object.values(reactFlowInstance.toObject()));
    }
  }, [save]);

  const validateNode = useCallback(
    debounce(async () => {
      try {
        const response = await fetch(`/validate/node/${data.id}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(reactFlowInstance.toObject()),
        });

        if (response.status === 200) {
          let jsonResponse = await response.json();
          let jsonResponseParsed = await JSON.parse(jsonResponse);
          setValidationStatus(jsonResponseParsed);
        }
      } catch (error) {
        // console.error("Error validating node:", error);
        setValidationStatus("error");
      }
    }, 1000), // Adjust the debounce delay (500ms) as needed
    [reactFlowInstance, data.id]
  );
  useEffect(() => {
    if (params.length > 0) {
      validateNode();
    }
  }, [params, validateNode]);

  if (!Icon) {
    if (showError.current) {
      setErrorData({
        title: data.type
          ? `The ${data.type} node could not be rendered, please review your json file`
          : "There was a node that can't be rendered, please review your json file",
      });
      showError.current = false;
    }
    deleteNode(data.id);
    return;
  }
  console.log(data);

  return (
    <div
      className={classNames(
        selected ? "border border-blue-500" : "border dark:border-gray-700",
        "prompt-node relative flex w-96 flex-col justify-center rounded-lg bg-white dark:bg-gray-900"
      )}
    >
      <div className="flex w-full items-center justify-between gap-8 rounded-t-lg border-b bg-gray-50 p-4 dark:border-b-gray-700 dark:bg-gray-800 dark:text-white ">
        <div className="flex w-full items-center gap-2 truncate text-lg">
          <Icon
            className="h-10 w-10 rounded p-1"
            style={{
              color: nodeColors[types[data.type]] ?? nodeColors.unknown,
            }}
          />
          <div className="ml-2 truncate">
            <ShadTooltip delayDuration={1500} content={data.type}>
              <div className="ml-2 truncate">{data.type}</div>
            </ShadTooltip>
          </div>
        </div>
        <div className="flex gap-3">
          <button
            className="relative"
            onClick={(event) => {
              event.preventDefault();
              openPopUp(<NodeModal data={data} />);
            }}
          >
            <div className=" absolute -right-1 -top-2 text-red-600">
              {Object.keys(data.node.template).some(
                (t) =>
                  data.node.template[t].advanced &&
                  data.node.template[t].required
              )
                ? " *"
                : ""}
            </div>
            <Cog6ToothIcon
              className={classNames(
                Object.keys(data.node.template).some(
                  (t) =>
                    data.node.template[t].advanced && data.node.template[t].show
                )
                  ? ""
                  : "hidden",
                "w-5 h-5  dark:text-gray-300"
              )}
            ></Cog6ToothIcon>
          </button>

          <button
            onClick={() => {
              deleteNode(data.id);
            }}
          >
            <TrashIcon className="w-5 h-5 dark:text-gray-300"></TrashIcon>
          </button>

          <div>
            <Tooltip
              title={
                !validationStatus ? (
                  "Validating..."
                ) : (
                  <div className="max-h-96 overflow-auto">
                    {validationStatus.params.split("\n").map((line, index) => (
                      <div key={index}>{line}</div>
                    ))}
                  </div>
                )
              }
            >
              <div className="w-5 h-5 relative top-[3px]">
                <div
                  className={classNames(
                    validationStatus && validationStatus.valid
                      ? "w-4 h-4 rounded-full bg-green-500 opacity-100"
                      : "w-4 h-4 rounded-full bg-gray-500 opacity-0 hidden animate-spin",
                    "absolute w-4 hover:text-gray-500 hover:dark:text-gray-300 transition-all ease-in-out duration-200"
                  )}
                ></div>
                <div
                  className={classNames(
                    validationStatus && !validationStatus.valid
                      ? "w-4 h-4 rounded-full  bg-red-500 opacity-100"
                      : "w-4 h-4 rounded-full bg-gray-500 opacity-0 hidden animate-spin",
                    "absolute w-4 hover:text-gray-500 hover:dark:text-gray-300 transition-all ease-in-out duration-200"
                  )}
                ></div>
                <div
                  className={classNames(
                    !validationStatus
                      ? "w-4 h-4 rounded-full  bg-yellow-500 opacity-100"
                      : "w-4 h-4 rounded-full bg-gray-500 opacity-0 hidden animate-spin",
                    "absolute w-4 hover:text-gray-500 hover:dark:text-gray-300 transition-all ease-in-out duration-200"
                  )}
                ></div>
              </div>
            </Tooltip>
          </div>
        </div>
      </div>

      <div className="h-full w-full py-5">
        <div className="w-full px-5 pb-3 text-sm text-gray-500 dark:text-gray-300">
          {data.node.description}
        </div>

        <>
          {Object.keys(data.node.template)
            .filter((t) => t.charAt(0) !== "_")
            .map((t: string, idx) => (
              <div key={idx}>
                {/* {idx === 0 ? (
									<div
										className={classNames(
											"px-5 py-2 mt-2 dark:text-white text-center",
											Object.keys(data.node.template).filter(
												(key) =>
													!key.startsWith("_") &&
													data.node.template[key].show &&
													!data.node.template[key].advanced
											).length === 0
												? "hidden"
												: ""
										)}
									>
										Inputs
									</div>
								) : (
									<></>
								)} */}
                {data.node.template[t].show &&
                !data.node.template[t].advanced ? (
                  <ParameterComponent
                    data={data}
                    color={
                      nodeColors[types[data.node.template[t].type]] ??
                      nodeColors.unknown
                    }
                    title={
                      data.node.template[t].display_name
                        ? data.node.template[t].display_name
                        : data.node.template[t].name
                        ? toTitleCase(data.node.template[t].name)
                        : toTitleCase(t)
                    }
                    name={t}
                    tooltipTitle={data.node.template[t].type}
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
          <div
            className={classNames(
              Object.keys(data.node.template).length < 1 ? "hidden" : "",
              "flex w-full justify-center"
            )}
          >
            {" "}
          </div>
          {/* <div className="px-5 py-2 mt-2 dark:text-white text-center">
						Output
					</div> */}
          <ParameterComponent
            data={data}
            color={nodeColors[types[data.type]] ?? nodeColors.unknown}
            title={data.type}
            tooltipTitle={`${data.node.base_classes.join("\n")}`}
            id={[data.type, data.id, ...data.node.base_classes].join("|")}
            type={data.node.base_classes.join("|")}
            left={false}
          />
        </>
      </div>
    </div>
  );
}
