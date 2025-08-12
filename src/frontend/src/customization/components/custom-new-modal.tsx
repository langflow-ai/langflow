import IOModal from "@/modals/IOModal/playground-modal";
import type { IOModalPropsType } from "@/types/components";

export function CustomIOModal({
	open,
	children,
	setOpen,
	disable,
	isPlayground,
}: IOModalPropsType) {
	return (
		<IOModal
			open={open}
			setOpen={setOpen}
			disable={disable}
			isPlayground={isPlayground}
		>
			{children}
		</IOModal>
	);
}
