import { Transition } from "@headlessui/react";
import { Bars3CenterLeftIcon } from "@heroicons/react/24/outline";
import { nodeColors } from "../../../utils";

export default function ChatTrigger({open, setOpen}){
    return(<Transition
        show={!open}
        appear={true}
        enter="transition ease-out duration-300"
        enterFrom="translate-y-96"
        enterTo="translate-y-0"
        leave="transition ease-in duration-300"
        leaveFrom="translate-y-0"
        leaveTo="translate-y-96"
    >
        <div className="absolute bottom-0 right-1">
            <div className="border flex justify-center align-center py-1 px-3 rounded-xl rounded-b-none bg-white dark:bg-gray-800 dark:border-gray-600 dark:text-white shadow">
                <button
                    onClick={() => {
                        setOpen(true);
                    }}
                >
                    <div className="flex gap-3  items-center">
                        <Bars3CenterLeftIcon
                            className="h-6 w-6 mt-1"
                            style={{ color: nodeColors["chat"] }}
                        />
                        Chat
                    </div>
                </button>
            </div>
        </div>
    </Transition>)
}