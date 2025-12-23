import AuthenticatedImage from "@/modals/IOModal/components/chatView/fileComponent/components/authenticated-image";

interface CustomAuthenticatedImageProps {
  src: string;
  alt: string;
  className?: string;
}

export default function CustomAuthenticatedImage({
  src,
  alt,
  className,
}: CustomAuthenticatedImageProps) {
  return (
    <AuthenticatedImage src={src} alt={alt} className={className} />
  );
}
