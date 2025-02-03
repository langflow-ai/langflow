import { MorphingMenu } from "@/components/ui/morphing-menu";

export default function ImportButtonComponent({}: {}) {
  const items = [
    {
      icon: "GoogleDrive",
      label: "Drive",
      onClick: () => {
        // Handle Google Drive click
      },
    },
    {
      icon: "OneDrive",
      label: "OneDrive",
      onClick: () => {
        // Handle OneDrive click
      },
    },
    {
      icon: "AWSInverted",
      label: "S3 Bucket",
      onClick: () => {
        // Handle S3 click
      },
    },
  ];

  return <MorphingMenu trigger="Import from..." items={items} />;
}
