import {
  ReactNode,
  forwardRef,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import EditFlowSettings from "../../components/EditFlowSettingsComponent";
import IconComponent from "../../components/genericIconComponent";
import { TagsSelector } from "../../components/tagsSelectorComponent";
import ToggleShadComponent from "../../components/toggleShadComponent";
import { Button } from "../../components/ui/button";
import { Checkbox } from "../../components/ui/checkbox";
import { alertContext } from "../../contexts/alertContext";
import { FlowsContext } from "../../contexts/flowsContext";
import { getStoreTags, saveFlowStore } from "../../controllers/API";
import { FlowType } from "../../types/flow";
import { removeApiKeys } from "../../utils/reactflowUtils";
import { getTagsIds } from "../../utils/storeUtils";
import BaseModal from "../baseModal";

const ShareModal = forwardRef(
  (
    props: {
      children?: ReactNode;
      is_component: boolean;
      component: FlowType;
      open?: boolean;
      setOpen?: (open: boolean) => void;
    },
    ref
  ): JSX.Element => {
    const { version, addFlow } = useContext(FlowsContext);
    const { setSuccessData, setErrorData } = useContext(alertContext);
    const [checked, setChecked] = useState(true);
    const [name, setName] = useState(props.component?.name ?? "");
    const [description, setDescription] = useState(
      props.component?.description ?? ""
    );
    const [open, setOpen] = useState(props.children ? false : true);

    const nameComponent = props.is_component ? "Component" : "Flow";

    const [tags, setTags] = useState<string[]>([]);
    const [sharePublic, setSharePublic] = useState(true);
    const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set());
    const tagListId = useRef<{ id: string; name: string }[]>([]);

    useEffect(() => {
      getStoreTags().then((res) => {
        tagListId.current = res;
        let tags = res.map((tag) => tag.name);
        setTags(tags);
      });
    }, []);

    useEffect(() => {
      setName(props.component?.name ?? "");
      setDescription(props.component?.description ?? "");
    }, [props.component]);

    function handleTagSelection(tag: string) {
      setSelectedTags((prev) => {
        const newSet = new Set(prev);
        if (newSet.has(tag)) {
          newSet.delete(tag);
        } else {
          newSet.add(tag);
        }
        return newSet;
      });
    }

    const handleShareComponent = () => {
      const saveFlow: FlowType = checked
        ? {
            id: props.component!.id,
            data: props.component!.data,
            description,
            name,
            last_tested_version: version,
            is_component: props.is_component,
          }
        : removeApiKeys({
            id: props.component!.id,
            data: props.component!.data,
            description,
            name,
            last_tested_version: version,
            is_component: props.is_component,
          });
      saveFlowStore(
        saveFlow,
        getTagsIds(Array.from(selectedTags), tagListId),
        sharePublic
      ).then(
        () => {
          if (props.is_component) {
            addFlow(true, saveFlow);
          }
          setSuccessData({
            title: `${nameComponent} shared successfully`,
          });
        },
        (err) => {
          setErrorData({
            title: "Error sharing flow",
            list: [err["response"]["data"]["detail"]],
          });
        }
      );
    };

    return (
      <BaseModal
        size="smaller-h-full"
        open={props.open ?? open}
        setOpen={props.setOpen ?? setOpen}
      >
        <BaseModal.Trigger>
          {props.children ? props.children : <></>}
        </BaseModal.Trigger>
        <BaseModal.Header
          description={`Share your ${nameComponent} to the Langflow Store`}
        >
          <span className="pr-2">Share</span>
          <IconComponent
            name="Share2"
            className="h-6 w-6 pl-1 text-foreground"
            aria-hidden="true"
          />
        </BaseModal.Header>
        <BaseModal.Content>
          <EditFlowSettings
            name={name}
            description={description}
            setName={setName}
            setDescription={setDescription}
          />
          <div className="mt-3 flex items-center space-x-2">
            <Checkbox
              id="terms"
              checked={checked}
              onCheckedChange={(event: boolean) => {
                setChecked(event);
              }}
            />
            <label htmlFor="terms" className="export-modal-save-api text-sm ">
              Save with my API keys
            </label>
          </div>
          <span className=" text-xs text-destructive ">
            Caution: Uncheck this box only removes API keys from fields
            specifically designated for API keys.
          </span>
          <div className="flex h-full w-full flex-col gap-3">
            <div className="flex justify-start pt-4 align-middle">
              <ToggleShadComponent
                disabled={false}
                size="medium"
                setEnabled={setSharePublic}
                enabled={sharePublic}
              />
              <div
                className="cursor-pointer pl-1"
                onClick={() => {
                  setSharePublic(!sharePublic);
                }}
              >
                {sharePublic ? (
                  <span>
                    This flow will be avaliable <b>for everyone</b>
                  </span>
                ) : (
                  <span>
                    This flow will be avaliable <b>just for you</b>
                  </span>
                )}
              </div>
            </div>
            <div className="w-full pt-2">
              <span className="text-sm">
                Add some tags to your {nameComponent}
              </span>
              <TagsSelector
                tags={tags}
                selectedTags={selectedTags}
                setSelectedTags={handleTagSelection}
              />
            </div>
          </div>
        </BaseModal.Content>

        <BaseModal.Footer>
          <Button
            onClick={() => {
              handleShareComponent();
              if (props.setOpen) props.setOpen(false);
              else setOpen(false);
            }}
            type="button"
          >
            {props.is_component ? "Save and " : ""}Share{" "}
            {!props.is_component ? "Flow" : ""}
          </Button>
        </BaseModal.Footer>
      </BaseModal>
    );
  }
);
export default ShareModal;
