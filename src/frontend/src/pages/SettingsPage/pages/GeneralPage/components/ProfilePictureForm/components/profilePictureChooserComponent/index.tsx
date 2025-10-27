import { useEffect, useRef } from "react";
import type { ProfilePicturesQueryResponse } from "@/controllers/API/queries/files";
import { customPreLoadImageUrl } from "@/customization/utils/custom-pre-load-image-url";
import { Button } from "../../../../../../../../components/ui/button";
import Loading from "../../../../../../../../components/ui/loading";
import { useDarkStore } from "../../../../../../../../stores/darkStore";
import { cn } from "../../../../../../../../utils/utils";

export type ProfilePictureChooserComponentProps = {
  profilePictures?: ProfilePicturesQueryResponse;
  loading: boolean;
  value: string;
  onChange: (value: string) => void;
};

export default function ProfilePictureChooserComponent({
  profilePictures,
  loading,
  value,
  onChange,
}: ProfilePictureChooserComponentProps) {
  const ref = useRef<HTMLButtonElement>(null);
  const dark = useDarkStore((state) => state.dark);

  useEffect(() => {
    if (value && ref) {
      ref.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [ref, value]);

  return (
    <div className="flex flex-col justify-center gap-2">
      {loading && !profilePictures ? (
        <Loading />
      ) : !profilePictures || Object.keys(profilePictures).length === 0 ? (
        <div className="text-sm text-muted-foreground py-4 text-center">
          No profile pictures available
        </div>
      ) : (
        Object.keys(profilePictures).map((folder, index) => (
          <div className="flex flex-col gap-2" key={index}>
            <div className="edit-flow-arrangement">
              <span className="font-normal">{folder}</span>
            </div>
            <div className="block overflow-hidden">
              <div className="flex items-center gap-1 overflow-x-auto rounded-lg bg-muted px-1 custom-scroll">
                {profilePictures[folder].map((path, idx) => (
                  <Button
                    key={idx}
                    ref={value === folder + "/" + path ? ref : undefined}
                    unstyled
                    onClick={() => onChange(folder + "/" + path)}
                    className="shrink-0 px-0.5 py-2"
                  >
                    <img
                      key={idx}
                      src={customPreLoadImageUrl(`${folder}/${path}`)}
                      style={{
                        filter:
                          value === folder + "/" + path
                            ? dark
                              ? "drop-shadow(0 0 0.3rem rgb(255, 255, 255))"
                              : "drop-shadow(0 0 0.3rem rgb(0, 0, 0))"
                            : "",
                      }}
                      className={cn("h-12 w-12")}
                    />
                  </Button>
                ))}
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
