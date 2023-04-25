import { Transition } from "@headlessui/react";
import {
	Bars3CenterLeftIcon,
	LockClosedIcon,
	PaperAirplaneIcon,
	XMarkIcon,
} from "@heroicons/react/24/outline";
import {
	MouseEventHandler,
	useContext,
	useEffect,
	useRef,
	useState,
} from "react";
import { sendAll } from "../../controllers/API";
import { alertContext } from "../../contexts/alertContext";
import { classNames, nodeColors, snakeToNormalCase } from "../../utils";
import { TabsContext } from "../../contexts/tabsContext";
import { ChatType } from "../../types/chat";
import ChatMessage from "./chatMessage";
import { NodeType } from "../../types/flow";
import ChatTrigger from "./chatTrigger";
import ChatModal from "../../modals/chatModal";

const _ = require("lodash");

export default function Chat({ flow }: ChatType) {
	const [open, setOpen] = useState(false);
	return (
		<>
			<ChatModal flow={flow} open={open} setOpen={setOpen} />
			<ChatTrigger open={open} setOpen={setOpen} flow={flow} />
		</>
	);
}
