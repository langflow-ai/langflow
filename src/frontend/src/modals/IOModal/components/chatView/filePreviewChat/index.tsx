import React, { useState } from "react";
import LoadingComponent from "../../../../../components/loadingComponent";
import IconComponent from "../../../../../components/genericIconComponent";

export default function FilePreview({ error, file, loading,onDelete }: { loading: boolean, file: File, error: boolean,onDelete:()=>void }) {
    const [isHovered, setIsHovered] = useState(false);

    return (
        <div className="inline-block relative w-56">
            {loading && <LoadingComponent remSize={5} />}
            {error && <div>Error...</div>}
            <div
                className={`rounded-md overflow-hidden transition duration-300 bg-background p-4 relative ${
                    isHovered ? "shadow-md" : ""
                }`}
                onMouseEnter={() => setIsHovered(true)}
                onMouseLeave={() => setIsHovered(false)}
            >
                <img src={URL.createObjectURL(file)} alt="file" className="w-full h-auto block" />
                {isHovered && (
                    <div className="absolute inset-0 bg-black bg-opacity-30 flex items-center justify-center">
                        <div
                            className="bg-white bg-opacity-80 rounded-full cursor-pointer p-2"
                            onClick={onDelete}
                        >
                            <IconComponent name="trash" className="stroke-red-500" />
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
