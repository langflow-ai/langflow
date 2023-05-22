import { Disclosure } from "@headlessui/react";
import { ChevronLeftIcon } from "@heroicons/react/24/outline";
import { useContext } from "react";
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
        } flex flex-shrink-0 flex-col overflow-hidden border-r transition-all duration-500 dark:border-r-gray-700`}
      >
        <div className="flex h-full w-52 flex-col  items-start overflow-y-auto border scrollbar-hide dark:border-gray-700 dark:bg-gray-800">
          <div className="flex w-full justify-between px-4 pt-1 align-middle">
            <span className="py-[2px] font-medium text-gray-900 dark:text-white ">
              {extraNavigation.title}
            </span>
          </div>
          <div className="flex w-full flex-grow flex-col">
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
                            "group flex w-full items-center rounded-md py-2 pl-2 text-sm font-medium"
                          )}
                        >
                          <item.icon
                            className={classNames(
                              item.href.split("/")[2] === current[4]
                                ? "text-gray-500"
                                : "text-gray-400 group-hover:text-gray-500",
                              "mr-3 h-6 w-6 flex-shrink-0"
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
                                "group flex w-full items-center rounded-md py-2 pl-2 pr-1 text-left text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
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
                                    ? "rotate-90 text-gray-400"
                                    : "text-gray-300",
                                  "transition-rotate ml-3 h-5 w-5 flex-shrink-0 duration-150 ease-in-out group-hover:text-gray-400"
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
