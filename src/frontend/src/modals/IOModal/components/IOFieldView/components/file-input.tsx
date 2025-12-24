import { useEffect, useState } from "react";

import { api } from "@/controllers/API/api";
import { getBaseUrl } from "@/customization/utils/urls";
import { createFileUpload } from "@/helpers/create-file-upload";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";
import useAlertStore from "@/stores/alertStore";
import IconComponent from "../../../../../components/common/genericIconComponent";
import { Button } from "../../../../../components/ui/button";
import { ALLOWED_IMAGE_INPUT_EXTENSIONS } from "../../../../../constants/constants";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import type { IOFileInputProps } from "../../../../../types/components";
import { customUsePostUploadFile } from "@/customization/hooks/use-custom-upload-file-v1";

export default function IOFileInput({ field, updateValue }: IOFileInputProps) {
  //component to handle file upload from chatIO
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  const [isDragging, setIsDragging] = useState(false);
  const [filePath, setFilePath] = useState("");
  const [image, setImage] = useState<string | null>(null);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { validateFileSize } = useFileSizeValidator();

  useEffect(() => {
    if (filePath) {
      updateValue(filePath, "file");
    }
  }, [filePath]);

  useEffect(() => {
    if (field && typeof field === "string") {
      // Use the path directly from field (format: flowId/filename)
      const imageUrl = `${getBaseUrl()}files/images/${field}`;

      // Fetch image with authentication
      api
        .get(imageUrl, { responseType: "blob" })
        .then((response) => {
          const objectUrl = URL.createObjectURL(response.data);
          setImage(objectUrl);
        })
        .catch((err) => {
          console.error("Failed to fetch authenticated image:", err);
        });
    }
  }, [field]);

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

  const { mutate } = customUsePostUploadFile();

  const upload = async (file) => {
    if (file) {
      try {
        validateFileSize(file);
      } catch (e) {
        if (e instanceof Error) {
          setErrorData({
            title: e.message,
          });
        }
        return;
      }
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
      mutate(
        { file, id: currentFlowId },
        {
          onSuccess: (data) => {
            const { file_path } = data;
            setFilePath(file_path);
          },
          onError: (error) => {
            setErrorData({
              title: "Error uploading file",
              list: [error.response?.data?.detail],
            });
            console.error("Error occurred while uploading file");
          },
        },
      );
    }
  };

  const handleButtonClick = (): void => {
    createFileUpload({
      multiple: false,
      accept: ALLOWED_IMAGE_INPUT_EXTENSIONS.join(","),
    }).then((files) => upload(files[0]));
    // Create a file input element
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
            className="order-last h-12 w-12 rounded-full object-cover"
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
