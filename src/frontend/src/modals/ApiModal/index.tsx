import { Dialog, Transition } from "@headlessui/react";
import { IconCheck, IconClipboard, IconDownload } from "@tabler/icons-react";
import {
  XMarkIcon,
  CommandLineIcon,
  CodeBracketSquareIcon,
} from "@heroicons/react/24/outline";
import { Fragment, useContext, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
import "ace-builds/src-noconflict/ext-language_tools";
// import "ace-builds/webpack-resolver";
import { darkContext } from "../../contexts/darkContext";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";

export default function ApiModal({ flowName }) {
  const [open, setOpen] = useState(true);
  const { dark } = useContext(darkContext);
  const { closePopUp } = useContext(PopUpContext);
  const [activeTab, setActiveTab] = useState(0);
  const ref = useRef();
  const [isCopied, setIsCopied] = useState<Boolean>(false);

  const copyToClipboard = () => {
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      return;
    }

    navigator.clipboard.writeText(tabs[activeTab].code).then(() => {
      setIsCopied(true);

      setTimeout(() => {
        setIsCopied(false);
      }, 2000);
    });
  };
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setTimeout(() => {
        closePopUp();
      }, 300);
    }
  }

  const pythonApiCode = `import requests
import json

API_URL = "${window.location.protocol}//${window.location.host}/predict"

def predict(message):
    with open("${flowName}.json", "r") as f:
        json_data = json.load(f)
    payload = {'exported_flow': json_data, 'message': message}
    response = requests.post(API_URL, json=payload)
    return response.json() # JSON {"result": "Response"}

print(predict("Your message"))`;

  const pythonCode = `from langflow import load_flow_from_json

flow = load_flow_from_json("${flowName}.json")
# Now you can use it like any chain
flow("Hey, have you heard of LangFlow?")`;

  const tabs = [
    {
      name: "Python API",
      mode: "python",
      image:
        "https://images.squarespace-cdn.com/content/v1/5df3d8c5d2be5962e4f87890/1628015119369-OY4TV3XJJ53ECO0W2OLQ/Python+API+Training+Logo.png?format=1000w",
      code: pythonApiCode,
    },
    {
      name: "Python Code",
      mode: "python",
      image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
      code: pythonCode,
    },
  ];
  return (
    <Transition.Root show={open} appear={true} as={Fragment}>
      <Dialog
        as="div"
        className="relative z-10"
        onClose={setModalOpen}
        initialFocus={ref}
      >
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity dark:bg-gray-600 dark:bg-opacity-75" />
        </Transition.Child>

        <div className="fixed inset-0 z-10 overflow-y-auto">
          <div className="flex h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            >
              <Dialog.Panel className="relative flex h-[600px] w-[700px] transform flex-col justify-between overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all dark:bg-gray-800 sm:my-8">
                <div className=" absolute right-0 top-0 z-50 hidden pr-4 pt-4 sm:block">
                  <button
                    type="button"
                    className="rounded-md text-gray-400 hover:text-gray-500"
                    onClick={() => {
                      setModalOpen(false);
                    }}
                  >
                    <span className="sr-only">Close</span>
                    <XMarkIcon className="h-6 w-6" aria-hidden="true" />
                  </button>
                </div>
                <div className="flex h-full w-full flex-col items-center justify-center">
                  <div className="z-10 flex w-full justify-center pb-4 shadow-sm">
                    <div className="mx-auto mt-4 flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 dark:bg-gray-900 sm:mx-0 sm:h-10 sm:w-10">
                      <CodeBracketSquareIcon
                        className="h-6 w-6 text-blue-600"
                        aria-hidden="true"
                      />
                    </div>
                    <div className="mt-4 text-center sm:ml-4 sm:text-left">
                      <Dialog.Title
                        as="h3"
                        className="text-lg font-medium leading-10 text-gray-900 dark:text-white"
                      >
                        Code
                      </Dialog.Title>
                    </div>
                  </div>
                  <div className="flex h-full w-full flex-row items-center justify-center gap-4 overflow-auto bg-gray-200 p-4 dark:bg-gray-900">
                    <div className="flex h-full w-full flex-col ">
                      <div className="z-10 flex px-5">
                        {tabs.map((tab, index) => (
                          <button
                            onClick={() => {
                              setActiveTab(index);
                            }}
                            className={
                              "-mr-px flex w-44 items-center justify-center gap-4 rounded-t-lg border border-b-0 border-gray-300 p-2 dark:border-gray-700 dark:text-gray-300 " +
                              (activeTab === index
                                ? " bg-white dark:bg-gray-800"
                                : "bg-gray-100 dark:bg-gray-900")
                            }
                          >
                            {tab.name}
                            <img src={tab.image} className="w-6" />
                          </button>
                        ))}
                      </div>
                      <div className="h-full w-full overflow-hidden rounded-lg bg-white px-4 py-5 shadow dark:bg-gray-800 sm:p-6">
                        <div className="mb-2 flex w-full items-center justify-between">
                          <span className="text-sm text-gray-500 dark:text-gray-300">
                            Export your flow to use it with this code.
                          </span>
                          <button
                            className="flex items-center gap-1.5 rounded bg-none p-1 text-xs text-gray-500 dark:text-gray-300"
                            onClick={copyToClipboard}
                          >
                            {isCopied ? (
                              <IconCheck size={18} />
                            ) : (
                              <IconClipboard size={18} />
                            )}
                            {isCopied ? "Copied!" : "Copy code"}
                          </button>
                        </div>
                        <SyntaxHighlighter
                          className="h-[370px]"
                          language={tabs[activeTab].mode}
                          style={oneDark}
                          customStyle={{ margin: 0 }}
                        >
                          {tabs[activeTab].code}
                        </SyntaxHighlighter>
                      </div>
                    </div>
                  </div>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
}
