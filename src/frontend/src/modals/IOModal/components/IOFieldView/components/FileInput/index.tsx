import { Button } from "../../../../../../components/ui/button";

import { useEffect, useState } from "react";
import IconComponent from "../../../../../../components/genericIconComponent";
import { BASE_URL_API } from "../../../../../../constants/constants";
import { uploadFile } from "../../../../../../controllers/API";
import useFlowsManagerStore from "../../../../../../stores/flowsManagerStore";
import { IOFileInputProps } from "../../../../../../types/components";

export default function IOFileInput({ field, updateValue }: IOFileInputProps) {
  //component to handle file upload from chatIO
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  const [isDragging, setIsDragging] = useState(false);
  const [filePath, setFilePath] = useState("");
  const [image, setImage] = useState<string | null>(null);

  useEffect(() => {
    if (filePath) {
      updateValue(filePath, "file");
    }
  }, [filePath]);

  useEffect(() => {
    if (field) {
      const fileName = field.split("/")[1];
      const flowFileId = currentFlowId.toString();
      setImage(`${BASE_URL_API}files/images/${flowFileId}/${fileName}`);
    }
  }, []);

  const dragOver = (e) => {
    e.preventDefault();
    if (e.dataTransfer.types.some((types) => types === "Files")) {
      setIsDragging(true);
    }
  };

  const dragEnter = (e) => {
    if (e.dataTransfer.types.some((types) => types === "Files")) {
      setIsDragging(true);
    }
    e.preventDefault();
  };

  const dragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const onDrop = (e) => {
    e.preventDefault();

    if (e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];

      upload(file);

      const fileReader = new FileReader();
      fileReader.onload = (event) => {
        const imageDataUrl = event.target?.result as string;
        setImage(imageDataUrl);
      };
      fileReader.readAsDataURL(file);
    }
    setIsDragging(false);
  };

  const upload = async (file) => {
    if (file) {
      // Check if a file was selected
      const fileReader = new FileReader();
      fileReader.onload = (event) => {
        const imageDataUrl = event.target?.result as string;
        setImage(imageDataUrl);

        // Display the image on the screen
        const imgElement = document.createElement("img");
        imgElement.src = imageDataUrl;
        document.body.appendChild(imgElement); // Add the image to the body or replace this with your desired location
      };
      fileReader.readAsDataURL(file);

      uploadFile(file, currentFlowId)
        .then((res) => res.data)
        .then((data) => {
          // Get the file name from the response
          const { file_path, flowId } = data;
          setFilePath(file_path);
        })
        .catch(() => {
          console.error("Error occurred while uploading file");
        });
    }
  };

  const handleButtonClick = (): void => {
    // Create a file input element
    const input = document.createElement("input");
    input.type = "file";
    input.style.display = "none"; // Hidden from view
    input.multiple = false; // Allow only one file selection
    input.onchange = (event: Event): void => {
      // Get the selected file
      const file = (event.target as HTMLInputElement).files?.[0];
      upload(file);
    };
    // Trigger the file selection dialog
    input.click();
  };

  return (
    <>
      <div
        onDragOver={dragOver}
        onDragEnter={dragEnter}
        onDragLeave={dragLeave}
        onDrop={onDrop}
        className={
          "flex h-full w-full items-center justify-between" +
          (isDragging
            ? "flex h-28 flex-col items-center justify-center gap-4 text-xs font-light"
            : "")
        }
      >
        {!isDragging && (
          <Button variant="primary" onClick={handleButtonClick}>
            Upload or drop your file
          </Button>
        )}

        {isDragging ? (
          <>
            <IconComponent name="ArrowUpToLine" className="h-5 w-5 stroke-1" />
            "Drop your file here"
          </>
        ) : image ? (
          <img
            className="order-last h-12 w-12 rounded-full object-cover "
            src={image ?? ""}
          />
        ) : (
          <>
            <IconComponent name="SunIcon" className="h-8 w-8 stroke-1" />
          </>
        )}
      </div>
    </>
  );
}
