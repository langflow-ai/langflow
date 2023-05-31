import React, { useContext } from "react";
import { Menu, Transition } from "@headlessui/react";
import { EllipsisVerticalIcon } from "@heroicons/react/20/solid";
import {
  Cog6ToothIcon,
  TrashIcon,
  PencilSquareIcon,
  DocumentDuplicateIcon,
  DocumentPlusIcon,
  Square2StackIcon,
} from "@heroicons/react/24/outline";
import { classNames } from "../../../../utils";
import { Fragment } from "react";
import NodeModal from "../../../../modals/NodeModal";
import { TabsContext } from "../../../../contexts/tabsContext";
import { useReactFlow } from "reactflow";
import EditNodeModal from "../../../../modals/EditNodeModal";

const NodeToolbarComponent = (props) => {
  const { setLastCopiedSelection, paste } = useContext(TabsContext);
  const reactFlowInstance = useReactFlow();
  return (
    <>
      <div className="h-10 w-26">
        <span className="isolate inline-flex rounded-md shadow-sm">
          <button
            className="hover:dark:hover:bg-[#242f47] text-gray-700 transition-all duration-500 ease-in-out dark:bg-gray-800 dark:text-gray-300 shadow-md relative inline-flex items-center rounded-l-md bg-white px-2 py-2 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:z-10"
            onClick={() => {
              props.deleteNode(props.data.id);
            }}
          >
            <TrashIcon className="w-5 h-5 dark:text-gray-300"></TrashIcon>
          </button>

          <button
            className={classNames(
              Object.keys(props.data.node.template).some(
                (t) =>
                  props.data.node.template[t].advanced &&
                  props.data.node.template[t].show
              )
                ? "hover:dark:hover:bg-[#242f47] text-gray-700 transition-all duration-500 ease-in-out dark:bg-gray-800 dark:text-gray-300 shadow-md relative -ml-px inline-flex items-center bg-white px-2 py-2  ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:z-10"
                : "hidden"
            )}
            onClick={(event) => {
              event.preventDefault();
              props.openPopUp(<NodeModal data={props.data} />);
            }}
          >
            <div className=" absolute right-1 top-0 text-red-600">
              {Object.keys(props.data.node.template).some(
                (t) =>
                  props.data.node.template[t].advanced &&
                  props.data.node.template[t].required
              )
                ? " *"
                : ""}
            </div>
            <Cog6ToothIcon
              className={classNames(
                Object.keys(props.data.node.template).some(
                  (t) =>
                    props.data.node.template[t].advanced &&
                    props.data.node.template[t].show
                )
                  ? ""
                  : "hidden",
                "w-5 h-5  dark:text-gray-300"
              )}
            ></Cog6ToothIcon>
          </button>

          <Menu as="div" className="relative inline-block text-left z-100">
            <button className="hover:dark:hover:bg-[#242f47] text-gray-700 transition-all duration-500 ease-in-out dark:bg-gray-800 dark:text-gray-300 shadow-md relative -ml-px inline-flex items-center bg-white px-2 py-2 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:z-10 rounded-r-md">
              <div>
                <Menu.Button className="flex items-center">
                  <EllipsisVerticalIcon
                    className="w-5 h-5 dark:text-gray-300"
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
                              ? "bg-gray-100 text-gray-900"
                              : "text-gray-700",
                            "w-full group flex items-center px-4 py-2 text-sm"
                          )}
                        >
                          <PencilSquareIcon
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
                              ? "bg-gray-100 text-gray-900"
                              : "text-gray-700",
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
          </Menu>
        </span>
      </div>
    </>
  );
};

export default NodeToolbarComponent;
