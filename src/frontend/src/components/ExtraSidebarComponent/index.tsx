import { Disclosure } from "@headlessui/react";
import { ChevronLeftIcon } from "@heroicons/react/24/outline";
import { useContext, useState } from "react";
import { Link } from "react-router-dom";
import { classNames } from "../../utils";
import { locationContext } from "../../contexts/locationContext";

export default function ExtraSidebar() {
  const {
    current,
    isStackedOpen,
    setIsStackedOpen,
    extraNavigation,
    extraComponent,
  } = useContext(locationContext);

  return (
    <>
      <aside
        className={` ${
          isStackedOpen ? "w-52" : "w-0 "
        } flex-shrink-0 flex overflow-hidden flex-col border-r dark:border-r-gray-700 transition-all duration-500`}
      >
        <div className="w-52 dark:bg-gray-800 border dark:border-gray-700  overflow-y-auto scrollbar-hide h-full flex flex-col items-start">
          <div className="flex px-4 justify-between align-middle w-full">
            <span className="text-gray-900 dark:text-white py-[2px] font-medium "></span>
          </div>
          <div className="flex flex-grow flex-col w-full">
            {extraNavigation.options ? (
              <div className="p-4">
                <nav className="flex-1 space-y-1">
                  {extraNavigation.options.map((item) =>
                    !item.children ? (
                      <div key={item.name}>
                        <Link
                          to={item.href}
                          className={classNames(
                            item.href.split("/")[2] === current[4]
                              ? "bg-gray-100 text-gray-900"
                              : "bg-white text-gray-600 hover:bg-gray-50 hover:text-gray-900",
                            "group w-full flex items-center pl-2 py-2 text-sm font-medium rounded-md"
                          )}
                        >
                          <item.icon
                            className={classNames(
                              item.href.split("/")[2] === current[4]
                                ? "text-gray-500"
                                : "text-gray-400 group-hover:text-gray-500",
                              "mr-3 flex-shrink-0 h-6 w-6"
                            )}
                          />
                          {item.name}
                        </Link>
                      </div>
                    ) : (
                      <Disclosure
                        as="div"
                        key={item.name}
                        className="space-y-1"
                      >
                        {({ open }) => (
                          <>
                            <Disclosure.Button
                              className={classNames(
                                item.href.split("/")[2] === current[4]
                                  ? "bg-gray-100 text-gray-900"
                                  : "bg-white text-gray-600 hover:bg-gray-50 hover:text-gray-900",
                                "group w-full flex items-center pl-2 pr-1 py-2 text-left text-sm font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                              )}
                            >
                              <item.icon
                                className="mr-3 h-6 w-6 flex-shrink-0 text-gray-400 group-hover:text-gray-500"
                                aria-hidden="true"
                              />
                              <span className="flex-1">{item.name}</span>
                              <svg
                                className={classNames(
                                  open
                                    ? "text-gray-400 rotate-90"
                                    : "text-gray-300",
                                  "ml-3 h-5 w-5 flex-shrink-0 transition-rotate duration-150 ease-in-out group-hover:text-gray-400"
                                )}
                                viewBox="0 0 20 20"
                                aria-hidden="true"
                              >
                                <path
                                  d="M6 6L14 10L6 14V6Z"
                                  fill="currentColor"
                                />
                              </svg>
                            </Disclosure.Button>
                            <Disclosure.Panel className="space-y-1">
                              {item.children.map((subItem) => (
                                <Link
                                  key={subItem.name}
                                  to={subItem.href}
                                  className={classNames(
                                    subItem.href.split("/")[3] === current[5]
                                      ? "bg-gray-100 text-gray-900"
                                      : "bg-white text-gray-600 hover:bg-gray-50 hover:text-gray-900",
                                    "group flex w-full items-center rounded-md py-2 pl-11 pr-2 text-sm font-medium"
                                  )}
                                >
                                  {subItem.name}
                                </Link>
                              ))}
                            </Disclosure.Panel>
                          </>
                        )}
                      </Disclosure>
                    )
                  )}
                </nav>
              </div>
            ) : (
              extraComponent
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
