import { useContext, useState } from "react";
import { Settings2, Copy, Trash2, FileText } from "lucide-react";
import { classNames } from "../../../../utils";
import { TabsContext } from "../../../../contexts/tabsContext";
import { useReactFlow } from "reactflow";
import EditNodeModal from "../../../../modals/EditNodeModal";
import ShadTooltip from "../../../../components/ShadTooltipComponent";

const NodeToolbarComponent = (props) => {
  const [nodeLength, setNodeLength] = useState(
    Object.keys(props.data.node.template).filter(
      (t) =>
        t.charAt(0) !== "_" &&
        props.data.node.template[t].show &&
        (props.data.node.template[t].type === "str" ||
          props.data.node.template[t].type === "bool" ||
          props.data.node.template[t].type === "float" ||
          props.data.node.template[t].type === "code" ||
          props.data.node.template[t].type === "prompt" ||
          props.data.node.template[t].type === "file" ||
          props.data.node.template[t].type === "Any" ||
          props.data.node.template[t].type === "int")
    ).length
  );

  const { setLastCopiedSelection, paste } = useContext(TabsContext);
  const reactFlowInstance = useReactFlow();
  return (
    <>
      <div className="h-10 w-26">
        <span className="isolate inline-flex rounded-md shadow-sm">
          <ShadTooltip content="Delete" side="top">
            <button
              className="hover:dark:hover:bg-[#242f47] text-foreground transition-all duration-500 ease-in-out dark:bg-gray-800 dark:text-muted-foreground shadow-md relative inline-flex items-center rounded-l-md bg-white px-2 py-2 ring-1 ring-inset ring-gray-300 hover:bg-muted focus:z-10"
              onClick={() => {
                props.deleteNode(props.data.id);
              }}
            >
              <Trash2 className="w-4 h-4 dark:text-muted-foreground"></Trash2>
            </button>
          </ShadTooltip>

          <ShadTooltip content="Duplicate" side="top">
            <button
              className={classNames(
                "hover:dark:hover:bg-[#242f47] text-foreground transition-all duration-500 ease-in-out dark:bg-gray-800 dark:text-muted-foreground shadow-md relative -ml-px inline-flex items-center bg-white px-2 py-2  ring-1 ring-inset ring-gray-300 hover:bg-muted focus:z-10"
              )}
              onClick={(event) => {
                event.preventDefault();
                // console.log(reactFlowInstance.getNode(props.data.id));
                paste(
                  {
                    nodes: [reactFlowInstance.getNode(props.data.id)],
                    edges: [],
                  },
                  {
                    x: 50,
                    y: 10,
                    paneX: reactFlowInstance.getNode(props.data.id).position.x,
                    paneY: reactFlowInstance.getNode(props.data.id).position.y,
                  }
                );
              }}
            >
              <Copy className="w-4 h-4 dark:text-muted-foreground"></Copy>
            </button>
          </ShadTooltip>

          <ShadTooltip
            content={
              props.data.node.documentation === ""
                ? "Coming Soon"
                : "Documentation"
            }
            side="top"
          >
            <a
              className={classNames(
                "hover:dark:hover:bg-[#242f47]  transition-all duration-500 ease-in-out dark:bg-gray-800 dark:text-muted-foreground shadow-md relative -ml-px inline-flex items-center bg-white px-2 py-2  ring-1 ring-inset ring-gray-300 hover:bg-muted focus:z-10" +
                  (props.data.node.documentation === ""
                    ? " text-muted-foreground"
                    : " text-foreground")
              )}
              target="_blank"
              rel="noopener noreferrer"
              href={props.data.node.documentation}
              // deactivate link if no documentation is provided
              onClick={(event) => {
                if (props.data.node.documentation === "") {
                  event.preventDefault();
                }
              }}
            >
              <FileText className="w-4 h-4 dark:text-muted-foreground"></FileText>
            </a>
          </ShadTooltip>

          <ShadTooltip content="Edit" side="top">
            <button
              className={classNames(
                "hover:dark:hover:bg-[#242f47]  transition-all duration-500 ease-in-out dark:bg-gray-800 dark:text-muted-foreground shadow-md relative -ml-px inline-flex items-center bg-white px-2 py-2  ring-1 ring-inset ring-gray-300 hover:bg-muted focus:z-10 rounded-r-md" +
                  (nodeLength == 0
                    ? " text-muted-foreground"
                    : " text-foreground")
              )}
              onClick={(event) => {
                if (nodeLength == 0) {
                  event.preventDefault();
                }
                event.preventDefault();
                props.openPopUp(<EditNodeModal data={props.data} />);
              }}
            >
              <Settings2 className="w-4 h-4 dark:text-muted-foreground"></Settings2>
            </button>
          </ShadTooltip>

          {/*
          <Menu as="div" className="relative inline-block text-left z-100">
            <button className="hover:dark:hover:bg-[#242f47] text-foreground transition-all duration-500 ease-in-out dark:bg-gray-800 dark:text-muted-foreground shadow-md relative -ml-px inline-flex items-center bg-white px-2 py-2 ring-1 ring-inset ring-gray-300 hover:bg-muted focus:z-10 rounded-r-md">
              <div>
                <Menu.Button className="flex items-center">
                  <EllipsisVerticalIcon
                    className="w-5 h-5 dark:text-muted-foreground"
                    aria-hidden="true"
                  />
                </Menu.Button>
              </div>

              <Transition
                as={Fragment}
                enter="transition ease-out duration-100"
                enterFrom="transform opacity-0 scale-95"
                enterTo="transform opacity-100 scale-100"
                leave="transition ease-in duration-75"
                leaveFrom="transform opacity-100 scale-100"
                leaveTo="transform opacity-0 scale-95"
              >
                <Menu.Items className="absolute z-40 mt-2 w-56 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none top-[28px]">
                  <div className="py-1">
                    <Menu.Item>
                      {({ active }) => (
                        <button
                          onClick={(event) => {
                            event.preventDefault();
                            props.openPopUp(
                              <EditNodeModal data={props.data} />
                            );
                          }}
                          className={classNames(
                            active
                              ? "bg-muted text-gray-900"
                              : "text-foreground",
                            "w-full group flex items-center px-4 py-2 text-sm"
                          )}
                        >
                          <Settings
                            className="mr-3 h-5 w-5 text-gray-400 group-hover:text-gray-500"
                            aria-hidden="true"
                          />
                          Edit
                        </button>
                      )}
                    </Menu.Item>
                    <Menu.Item>
                      {({ active }) => (
                        <button
                          onClick={(event) => {
                            event.preventDefault();
                            console.log(
                              reactFlowInstance.getNode(props.data.id)
                            );
                            paste(
                              {
                                nodes: [
                                  reactFlowInstance.getNode(props.data.id),
                                ],
                                edges: [],
                              },
                              {
                                x: 50,
                                y: 10,
                                paneX: reactFlowInstance.getNode(props.data.id)
                                  .position.x,
                                paneY: reactFlowInstance.getNode(props.data.id)
                                  .position.y,
                              }
                            );
                          }}
                          className={classNames(
                            active
                              ? "bg-muted text-gray-900"
                              : "text-foreground",
                            "w-full group flex items-center px-4 py-2 text-sm"
                          )}
                        >
                          <DocumentDuplicateIcon
                            className="mr-3 h-5 w-5 text-gray-400 group-hover:text-gray-500"
                            aria-hidden="true"
                          />
                          Duplicate
                        </button>
                      )}
                    </Menu.Item>
                  </div>
                </Menu.Items>
              </Transition>
            </button>
          </Menu> */}
        </span>
      </div>
    </>
  );
};

export default NodeToolbarComponent;
