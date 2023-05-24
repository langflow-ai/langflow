import {
  BugAntIcon,
  CheckCircleIcon,
  Cog6ToothIcon,
  EllipsisHorizontalCircleIcon,
  ExclamationCircleIcon,
  InformationCircleIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import { classNames, nodeColors, nodeIcons, toNormalCase } from "../../utils";
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
  const Icon = nodeIcons[types[data.type]];
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

  return (
    <div
      className={classNames(
        selected ? "border border-blue-500" : "border dark:border-gray-700",
        "prompt-node relative bg-white dark:bg-gray-900 w-96 rounded-lg flex flex-col justify-center"
      )}
    >
      <div className="w-full dark:text-white flex items-center justify-between p-4 gap-8 bg-gray-50 rounded-t-lg dark:bg-gray-800 border-b dark:border-b-gray-700 ">
        <div className="w-full flex items-center truncate gap-2 text-lg">
          <Icon
            className="w-10 h-10 p-1 rounded"
            style={{
              color: nodeColors[types[data.type]] ?? nodeColors.unknown,
            }}
          />
          <div className="ml-2 truncate">{data.type}</div>
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
              <div className="relative w-5 h-5">
                <CheckCircleIcon
                  className={classNames(
                    validationStatus && validationStatus.valid
                      ? "text-green-500 opacity-100"
                      : "text-green-500 opacity-0 animate-spin",
                    "absolute w-5 hover:text-gray-500 hover:dark:text-gray-300 transition-all ease-in-out duration-200"
                  )}
                />
                <ExclamationCircleIcon
                  className={classNames(
                    validationStatus && !validationStatus.valid
                      ? "text-red-500 opacity-100"
                      : "text-red-500 opacity-0 animate-spin",
                    "w-5 absolute hover:text-gray-500 hover:dark:text-gray-600 transition-all ease-in-out duration-200"
                  )}
                />
                <EllipsisHorizontalCircleIcon
                  className={classNames(
                    !validationStatus
                      ? "text-yellow-500 opacity-100"
                      : "text-yellow-500 opacity-0 animate-spin",
                    "w-5 absolute hover:text-gray-500 hover:dark:text-gray-600 transition-all ease-in-out duration-300"
                  )}
                />
              </div>
            </Tooltip>
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
            <div className=" absolute text-red-600 -top-2 -right-1">
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
                "w-6 h-6  dark:text-gray-300  hover:animate-spin"
              )}
            ></Cog6ToothIcon>
          </button>
          <button
            onClick={() => {
              deleteNode(data.id);
            }}
          >
            <TrashIcon className="w-6 h-6 hover:text-red-500 dark:text-gray-300 dark:hover:text-red-500"></TrashIcon>
          </button>
        </div>
      </div>

      <div className="w-full h-full py-5">
        <div className="w-full text-gray-500 dark:text-gray-300 px-5 pb-3 text-sm">
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
                        ? toNormalCase(data.node.template[t].name)
                        : toNormalCase(t)
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
          <div
            className={classNames(
              Object.keys(data.node.template).length < 1 ? "hidden" : "",
              "w-full flex justify-center"
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
            tooltipTitle={`Type: ${data.node.base_classes.join(" | ")}`}
            id={[data.type, data.id, ...data.node.base_classes].join("|")}
            type={data.node.base_classes.join("|")}
            left={false}
          />
        </>
      </div>
    </div>
  );
}
