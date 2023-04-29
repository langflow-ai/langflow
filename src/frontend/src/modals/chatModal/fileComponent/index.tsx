import {  CloudArrowDownIcon, DocumentIcon } from "@heroicons/react/24/outline";
import * as base64js from 'base64-js';

export default function FileCard({ fileName, content, fileType }) {
    const handleDownload = () => {
        const byteArray = new Uint8Array(base64js.toByteArray(content));
        const blob = new Blob([byteArray], { type: 'application/octet-stream' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = fileName+".png";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      };

	return (
		<button
			onClick={handleDownload}
			className="bg-gray-100 shadow rounded w-1/2 text-gray-700 hover:drop-shadow-lg px-2 py-2 flex justify-between items-center border border-gray-300"
		>
			<div className="flex gap-2 text-current items-center w-full mr-2">
				{" "}
				<DocumentIcon className="w-8 h-8" />
				<div className="flex flex-col items-start">
					{" "}
					<div className="truncate text-sm text-current">{fileName}</div>
                    <div className="truncate text-xs  text-gray-500">{fileType}</div>

				</div>
				<CloudArrowDownIcon className="w-6 h-6 text-current ml-auto" />
			</div>
		</button>
	);
}
