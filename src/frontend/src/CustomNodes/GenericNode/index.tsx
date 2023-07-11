import { Zap } from "lucide-react";
import { useContext, useEffect, useRef, useState } from "react";
import { NodeToolbar } from "reactflow";
import ShadTooltip from "../../components/ShadTooltipComponent";
import Tooltip from "../../components/TooltipComponent";
import { useSSE } from "../../contexts/SSEContext";
import { alertContext } from "../../contexts/alertContext";
import { PopUpContext } from "../../contexts/popUpContext";
import { typesContext } from "../../contexts/typesContext";
import NodeModal from "../../modals/NodeModal";
import NodeToolbarComponent from "../../pages/FlowPage/components/nodeToolbarComponent";
import { NodeDataType } from "../../types/flow";
import {
  classNames,
  nodeColors,
  nodeIconsLucide,
  toTitleCase,
} from "../../utils";
import ParameterComponent from "./components/parameterComponent";

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

  const { closePopUp, openPopUp } = useContext(PopUpContext);
  // any to avoid type conflict
  const Icon: any =
    nodeIconsLucide[data.type] || nodeIconsLucide[types[data.type]];
  const [validationStatus, setValidationStatus] = useState(null);
  // State for outline color
  const { sseData, isBuilding } = useSSE();
  const refHtml = useRef(null);

  // useEffect(() => {
  //   if (reactFlowInstance) {
  //     setParams(Object.values(reactFlowInstance.toObject()));
  //   }
  // }, [save]);

  // New useEffect to watch for changes in sseData and update validation status
  useEffect(() => {
    const relevantData = sseData[data.id];
    if (relevantData) {
      // Extract validation information from relevantData and update the validationStatus state
      setValidationStatus(relevantData);
    } else {
      setValidationStatus(null);
    }
  }, [sseData, data.id]);

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
  useEffect(() => {}, [closePopUp, data.node.template]);
  return (
    <>
      <NodeToolbar>
        <NodeToolbarComponent
          data={data}
          openPopUp={openPopUp}
          deleteNode={deleteNode}
        ></NodeToolbarComponent>
      </NodeToolbar>

      <div
        className={classNames(
          selected ? "border border-ring" : "border",
          "generic-node-div"
        )}
      >
        <div className="generic-node-div-title">
          <div className="generic-node-title-arrangement">
            <Icon
              strokeWidth={1.5}
              className="generic-node-icon"
              style={{
                color: nodeColors[types[data.type]] ?? nodeColors.unknown,
              }}
            />
            <div className="generic-node-tooltip-div">
              <ShadTooltip content={data.node.display_name}>
                <div className="generic-node-tooltip-div text-primary">
                  {data.node.display_name}
                </div>
              </ShadTooltip>
            </div>
          </div>
          <div className="round-button-div">
            <button
              className="relative"
              onClick={(event) => {
                event.preventDefault();
                openPopUp(<NodeModal data={data} />);
              }}
            ></button>
          </div>
          <div className="round-button-div">
            <div>
              <Tooltip
                title={
                  isBuilding ? (
                    <span>Building...</span>
                  ) : !validationStatus ? (
                    <span className="flex">
                      Build{" "}
                      <Zap
                        className="mx-0.5 h-5 fill-build-trigger stroke-build-trigger stroke-1"
                        strokeWidth={1.5}
                      />{" "}
                      flow to validate status.
                    </span>
                  ) : (
                    <div className="max-h-96 overflow-auto">
                      {validationStatus.params
                        ? validationStatus.params
                            .split("\n")
                            .map((line, index) => <div key={index}>{line}</div>)
                        : ""}
                    </div>
                  )
                }
              >
                <div className="generic-node-status-position">
                  <div
                    className={classNames(
                      validationStatus && validationStatus.valid
                        ? "green-status"
                        : "status-build-animation",
                      "status-div"
                    )}
                  ></div>
                  <div
                    className={classNames(
                      validationStatus && !validationStatus.valid
                        ? "red-status"
                        : "status-build-animation",
                      "status-div"
                    )}
                  ></div>
                  <div
                    className={classNames(
                      !validationStatus || isBuilding
                        ? "yellow-status"
                        : "status-build-animation",
                      "status-div"
                    )}
                  ></div>
                </div>
              </Tooltip>
            </div>
          </div>
        </div>

        <div className="generic-node-desc">
          <div className="generic-node-desc-text">{data.node.description}</div>

          <>
            {Object.keys(data.node.template)
              .filter((t) => t.charAt(0) !== "_")
              .map((t: string, idx) => (
                <div key={idx}>
                  {/* {idx === 0 ? (
                                <div
                                    className={classNames(
                                        "px-5 py-2 mt-2 text-center",
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
                        nodeColors[data.node.template[t].type] ??
                        nodeColors.unknown
                      }
                      title={
                        data.node.template[t].display_name
                          ? data.node.template[t].display_name
                          : data.node.template[t].name
                          ? toTitleCase(data.node.template[t].name)
                          : toTitleCase(t)
                      }
                      info={data.node.template[t].info}
                      name={t}
                      tooltipTitle={
                        data.node.template[t].input_types?.join("\n") ??
                        data.node.template[t].type
                      }
                      required={data.node.template[t].required}
                      id={
                        (data.node.template[t].input_types?.join(";") ??
                          data.node.template[t].type) +
                        "|" +
                        t +
                        "|" +
                        data.id
                      }
                      left={true}
                      type={data.node.template[t].type}
                      optionalHandle={data.node.template[t].input_types}
                    />
                  ) : (
                    <></>
                  )}
                </div>
              ))}
            <div
              className={classNames(
                Object.keys(data.node.template).length < 1 ? "hidden" : "",
                "flex-max-width justify-center"
              )}
            >
              {" "}
            </div>
            {/* <div className="px-5 py-2 mt-2 text-center">
                  Output
              </div> */}
            <ParameterComponent
              data={data}
              color={nodeColors[types[data.type]] ?? nodeColors.unknown}
              title={
                data.node.output_types && data.node.output_types.length > 0
                  ? data.node.output_types.join("|")
                  : data.type
              }
              tooltipTitle={data.node.base_classes.join("\n")}
              id={[data.type, data.id, ...data.node.base_classes].join("|")}
              type={data.node.base_classes.join("|")}
              left={false}
            />
          </>
        </div>
      </div>
    </>
  );
}
