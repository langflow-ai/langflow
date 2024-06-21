import "ace-builds/src-noconflict/ace";
import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
// import "ace-builds/webpack-resolver";
import { cloneDeep } from "lodash";
import { useEffect, useState } from "react";
import JsonView from "react18-json-view";
import "react18-json-view/src/dark.css";
import "react18-json-view/src/style.css";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import {
  CODE_DICT_DIALOG_SUBTITLE,
  TEXT_DIALOG_SUBTITLE,
} from "../../constants/constants";
import TextOutputView from "../../shared/components/textOutputView";
import { useDarkStore } from "../../stores/darkStore";
import BaseModal from "../baseModal";

export default function TextModal({
  children,
  value,
}: {
  children: JSX.Element;
  value: Object;
}): JSX.Element {
  const [open, setOpen] = useState(false);

  return (
    <BaseModal size="medium-h-full" open={open} setOpen={setOpen}>
      <BaseModal.Trigger className="h-full">{children}</BaseModal.Trigger>
      <BaseModal.Header description={""}>
        <span className="pr-2">View Text</span>
        <IconComponent
          name="Type"
          className="h-6 w-6 pl-1 text-primary"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex h-full w-full flex-col transition-all">
          <div className="h-[370px]">
            <TextOutputView value={value} left={false} />
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer>
        <div className="flex w-full justify-end pt-2">
          <Button className="flex gap-2 px-3" onClick={() => setOpen(false)}>
            Close
          </Button>
        </div>
      </BaseModal.Footer>
    </BaseModal>
  );
}
