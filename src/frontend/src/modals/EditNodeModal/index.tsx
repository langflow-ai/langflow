import { Dialog, Switch, Transition } from "@headlessui/react";
import {
  ChevronDoubleLeftIcon,
  ChevronDoubleRightIcon,
  PencilSquareIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import { Fragment, useContext, useEffect, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { NodeDataType } from "../../types/flow";
import { classNames, limitScrollFieldsModal, nodeIcons } from "../../utils";
import { typesContext } from "../../contexts/typesContext";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";

const invoices = [
  {
    invoice: "INV001",
    paymentStatus: "Paid",
    totalAmount: "$250.00",
    paymentMethod: "Credit Card",
  },
  {
    invoice: "INV002",
    paymentStatus: "Pending",
    totalAmount: "$150.00",
    paymentMethod: "PayPal",
  },
  {
    invoice: "INV003",
    paymentStatus: "Unpaid",
    totalAmount: "$350.00",
    paymentMethod: "Bank Transfer",
  },
  {
    invoice: "INV004",
    paymentStatus: "Paid",
    totalAmount: "$450.00",
    paymentMethod: "Credit Card",
  },
  {
    invoice: "INV005",
    paymentStatus: "Paid",
    totalAmount: "$550.00",
    paymentMethod: "PayPal",
  },
  {
    invoice: "INV006",
    paymentStatus: "Pending",
    totalAmount: "$200.00",
    paymentMethod: "Bank Transfer",
  },
  {
    invoice: "INV007",
    paymentStatus: "Unpaid",
    totalAmount: "$300.00",
    paymentMethod: "Credit Card",
  },
];

export default function EditNodeModal({ data }: { data: NodeDataType }) {
  const [open, setOpen] = useState(true);
  const { closePopUp } = useContext(PopUpContext);
  const { types } = useContext(typesContext);
  const ref = useRef();
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setTimeout(() => {
        closePopUp();
      }, 300);
    }
  }
  const [advanced, setAdvanced] = useState([]);
  const [parameters, setParameters] = useState([]);
  const [enabled, setEnabled] = useState(false);

  const updateAdvancedParameters = () => {
    setAdvanced(
      Object.keys(data.node.template).filter(
        (t) =>
          t.charAt(0) !== "_" &&
          data.node.template[t].advanced &&
          data.node.template[t].show
      )
    );
    setParameters(
      Object.keys(data.node.template).filter(
        (t) =>
          t.charAt(0) !== "_" &&
          !data.node.template[t].advanced &&
          data.node.template[t].show &&
          (data.node.template[t].type === "str" ||
            data.node.template[t].type === "bool" ||
            data.node.template[t].type === "float" ||
            data.node.template[t].type === "code" ||
            data.node.template[t].type === "prompt" ||
            data.node.template[t].type === "file" ||
            data.node.template[t].type === "Any" ||
            data.node.template[t].type === "int")
      )
    );
  };

  useEffect(() => {
    updateAdvancedParameters();
  }, [data.node.template]);

  console.log("DATA", data.node.template);

  const Icon = nodeIcons[types[data.type]];
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
          <div className="fixed inset-0 bg-gray-500 dark:bg-gray-600 dark:bg-opacity-75 bg-opacity-75 transition-opacity" />
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
              <Dialog.Panel className="relative flex flex-col justify-between transform h-[600px] overflow-hidden rounded-lg bg-white dark:bg-gray-800 text-left shadow-xl transition-all sm:my-8 w-[700px]">
                <div className=" z-50 absolute top-0 right-0 hidden pt-4 pr-4 sm:block">
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
                <div className="h-full w-full flex flex-col justify-center items-center">
                  <div className="flex w-full pb-4 z-10 justify-center shadow-sm">
                    <div className="mx-auto mt-4 flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 dark:bg-gray-900 sm:mx-0 sm:h-10 sm:w-10">
                      <PencilSquareIcon
                        className="h-6 w-6 text-blue-600"
                        aria-hidden="true"
                      />
                    </div>
                    <div className="mt-4 text-center sm:ml-4 sm:text-left">
                      <Dialog.Title
                        as="h3"
                        className="text-lg font-medium dark:text-white leading-10 text-gray-900"
                      >
                        Edit Node
                      </Dialog.Title>
                    </div>
                  </div>
                  <div className="h-full w-full bg-gray-200 dark:bg-gray-900 p-4 gap-4 flex flex-row justify-center items-center">
                    <div className="flex w-full h-full max-h-[445px]">
                      <div
                        className={classNames(
                          "w-full rounded-lg bg-white dark:bg-gray-800 shadow",
                          Object.keys(data.node.template).filter(
                            (t) =>
                              t.charAt(0) !== "_" &&
                              data.node.template[t].advanced &&
                              data.node.template[t].show
                          ).length > limitScrollFieldsModal ||
                            Object.keys(data.node.template).filter(
                              (t) =>
                                t.charAt(0) !== "_" &&
                                !data.node.template[t].advanced &&
                                data.node.template[t].show
                            ).length > limitScrollFieldsModal
                            ? "overflow-scroll overflow-x-hidden custom-scroll h-fit"
                            : "overflow-hidden h-fit"
                        )}
                      >
                        <div className="flex flex-col h-full gap-5 h-fit	">
                          <Table>
                            <TableCaption>
                              A list of your recent invoices.
                            </TableCaption>
                            <TableHeader>
                              <TableRow>
                                <TableHead className="w-[100px]">
                                  Invoice
                                </TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Method</TableHead>
                                <TableHead className="text-right">
                                  Amount
                                </TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {invoices.map((invoice) => (
                                <TableRow key={invoice.invoice}>
                                  <TableCell className="font-medium">
                                    {invoice.invoice}
                                  </TableCell>
                                  <TableCell>{invoice.paymentStatus}</TableCell>
                                  <TableCell>{invoice.paymentMethod}</TableCell>
                                  <TableCell className="text-right">
                                    {invoice.totalAmount}
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>

                          <table className="min-w-full divide-y divide-gray-300">
                            <thead className="bg-gray-50">
                              <tr>
                                <th
                                  scope="col"
                                  className="py-1 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6"
                                >
                                  Param
                                </th>
                                <th
                                  scope="col"
                                  className="px-3 py-1 text-left text-sm font-semibold text-gray-900"
                                >
                                  Value
                                </th>
                                <th
                                  scope="col"
                                  className="px-3 py-1 text-left text-sm font-semibold text-gray-900"
                                >
                                  Show
                                </th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200 bg-white">
                              {Object.keys(data.node.template)
                                .filter((t) => t.charAt(0) !== "_")
                                .map((n, i) => (
                                  <tr key={i}>
                                    <td className="whitespace-nowrap py-1 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6">
                                      {data.node.template[n].name
                                        ? data.node.template[n].name
                                        : data.node.template[n].display_name}
                                    </td>
                                    <td className="whitespace-nowrap px-3 py-1 text-sm text-gray-500">
                                      {data.node.template[n].value
                                        ? data.node.template[n].value
                                        : "-"}
                                    </td>
                                    <td className="whitespace-nowrap px-3 py-1 text-sm text-gray-500">
                                      <Switch
                                        checked={enabled}
                                        onChange={setEnabled}
                                        className="group relative inline-flex h-5 w-10 flex-shrink-0 cursor-pointer items-center justify-center rounded-full focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2"
                                      >
                                        <span className="sr-only">
                                          Use setting
                                        </span>
                                        <span
                                          aria-hidden="true"
                                          className="pointer-events-none absolute h-full w-full rounded-md bg-white"
                                        />
                                        <span
                                          aria-hidden="true"
                                          className={classNames(
                                            enabled
                                              ? "bg-indigo-600"
                                              : "bg-gray-200",
                                            "pointer-events-none absolute mx-auto h-4 w-9 rounded-full transition-colors duration-200 ease-in-out"
                                          )}
                                        />
                                        <span
                                          aria-hidden="true"
                                          className={classNames(
                                            enabled
                                              ? "translate-x-5"
                                              : "translate-x-0",
                                            "pointer-events-none absolute left-0 inline-block h-5 w-5 transform rounded-full border border-gray-200 bg-white shadow ring-0 transition-transform duration-200 ease-in-out"
                                          )}
                                        />
                                      </Switch>
                                    </td>
                                  </tr>
                                ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="bg-gray-200 dark:bg-gray-900 w-full pb-3 flex flex-row-reverse px-4">
                    <button
                      type="button"
                      className="inline-flex w-full justify-center rounded-md border border-transparent bg-indigo-600 px-4 py-2 text-base font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 sm:ml-3 sm:w-auto sm:text-sm"
                      onClick={() => {
                        setModalOpen(false);
                      }}
                    >
                      Done
                    </button>
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
