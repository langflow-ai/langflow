import ShadTooltip from "@/components/common/shadTooltipComponent";
import ForwardedIconComponent from "../../../../../../common/genericIconComponent";
import { Button } from "../../../../../../ui/button";

const UploadFileButton = ({
	fileInputRef,
	handleFileChange,
	handleButtonClick,
	isBuilding,
}) => {
	return (
		<ShadTooltip
			styleClasses="z-50"
			side="right"
			content="Attach image (png, jpg, jpeg)"
		>
			<div>
				<input
					disabled={isBuilding}
					type="file"
					ref={fileInputRef}
					style={{ display: "none" }}
					onChange={handleFileChange}
				/>
				<Button
					disabled={isBuilding}
					className={`h-7 w-7 px-0 flex items-center justify-center ${
						isBuilding
							? "cursor-not-allowed"
							: "text-muted-foreground hover:text-primary"
					}`}
					onClick={handleButtonClick}
					unstyled
				>
					<ForwardedIconComponent className="h-[18px] w-[18px]" name="Image" />
				</Button>
			</div>
		</ShadTooltip>
	);
};

export default UploadFileButton;
