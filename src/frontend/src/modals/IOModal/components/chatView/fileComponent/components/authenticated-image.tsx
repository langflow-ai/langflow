import { type AxiosError } from "axios";
import { type ReactElement, useEffect, useState } from "react";
import { api } from "@/controllers/API/api";
import Loading from "@/components/ui/loading";

export interface AuthenticatedImageProps {
  src: string;
  alt: string;
  className?: string;
}

type ImageState = "loading" | "success" | "error";

export default function AuthenticatedImage({
  src,
  alt,
  className,
}: AuthenticatedImageProps): ReactElement {
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [state, setState] = useState<ImageState>("loading");

  useEffect(() => {
    let isMounted = true;
    let objectUrl: string | null = null;

    const fetchImage = async (): Promise<void> => {
      try {
        setState("loading");

        const response = await api.get<Blob>(src, {
          responseType: "blob",
        });

        if (!isMounted) return;

        objectUrl = URL.createObjectURL(response.data);
        setImageSrc(objectUrl);
        setState("success");
      } catch (error) {
        if (!isMounted) return;

        const axiosError = error as AxiosError;
        console.error(
          `Failed to fetch image from ${src}:`,
          axiosError.message || "Unknown error",
        );
        setState("error");
      }
    };

    fetchImage();

    return () => {
      isMounted = false;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [src]);

  if (state === "loading") {
    return (
      <div
        className={`flex items-center justify-center bg-muted ${className ?? ""}`}
        style={{ minHeight: "80px" }}
        data-testid="authenticated-image-loading"
      >
        <Loading size={32} />
      </div>
    );
  }

  if (state === "error" || !imageSrc) {
    return (
      <div
        className={`flex items-center justify-center bg-muted text-sm text-muted-foreground ${className ?? ""}`}
        style={{ minHeight: "80px" }}
        data-testid="authenticated-image-error"
      >
        Failed to load image
      </div>
    );
  }

  return (
    <img
      src={imageSrc}
      alt={alt}
      className={className}
      data-testid="authenticated-image"
    />
  );
}
