import FileCard from "@/components/core/playgroundComponent/components/chatView/fileComponent/components/file-card";
import type { fileCardPropsType } from "@/types/components";

export function CustomFileCard({
	fileName,
	path,
	fileType,
	showFile = true,
}: fileCardPropsType) {
	return (
		<FileCard
			fileName={fileName}
			path={path}
			fileType={fileType}
			showFile={showFile}
		/>
	);
}

export default CustomFileCard;
