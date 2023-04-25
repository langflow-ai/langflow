import {
	useEffect,
	useRef,
	useState,
} from "react";

import { ChatType } from "../../types/chat";
import ChatTrigger from "./chatTrigger";
import ChatModal from "../../modals/chatModal";

const _ = require("lodash");

export default function Chat({ flow }: ChatType) {

	const [open, setOpen] = useState(false);
	useEffect(() => {
		const handleKeyDown = (event: KeyboardEvent) => {
			console.log(event)
		  if (event.key === "K" && event.shiftKey && (event.metaKey||event.ctrlKey)) {
			console.log("dfdsfds")
			setOpen(oldState=>!oldState);
		  }
		};
		document.addEventListener("keydown", handleKeyDown);
		return () => {
			document.removeEventListener("keydown", handleKeyDown);
		  };
		}, []);
	return (
		<>
			<ChatModal flow={flow} open={open} setOpen={setOpen} />
			<ChatTrigger open={open} setOpen={setOpen} flow={flow} />
		</>
	);
}
