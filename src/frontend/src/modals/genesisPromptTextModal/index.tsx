import { useEffect, useRef, useState } from "react";
import IconComponent from "../../components/common/genericIconComponent";
import { Button } from "../../components/ui/button";
import { Textarea } from "../../components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
import {
  EDIT_TEXT_PLACEHOLDER,
  TEXT_DIALOG_TITLE,
} from "../../constants/constants";
import { handleKeyDown } from "../../utils/reactflowUtils";
import { classNames } from "../../utils/utils";
import BaseModal from "../baseModal";

export type GenesisPromptTextModalProps = {
  value: string;
  setValue: (value: string) => void;
  disabled?: boolean;
  children?: React.ReactNode;
  readonly?: boolean;
  password?: boolean;
  changeVisibility?: () => void;
  onCloseModal?: () => void;
  // Genesis Prompt specific props
  promptId?: string;
  promptVersion?: number;
  versionStatus?: string;
  onSaveVersion?: (content: string, onSuccess?: () => void) => void;
  isSavingVersion?: boolean;
  onSubmitForReview?: (comment?: string) => void;
  isSubmittingForReview?: boolean;
};

export default function GenesisPromptTextModal({
  value,
  setValue,
  disabled,
  children,
  readonly = false,
  password,
  changeVisibility,
  onCloseModal,
  promptId,
  promptVersion,
  versionStatus,
  onSaveVersion,
  isSavingVersion,
  onSubmitForReview,
  isSubmittingForReview,
}: GenesisPromptTextModalProps): JSX.Element {
  const [modalOpen, setModalOpen] = useState(false);
  const [inputValue, setInputValue] = useState(value);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [showReviewDialog, setShowReviewDialog] = useState(false);
  const [reviewComment, setReviewComment] = useState("");
  const [hasSubmittedForReview, setHasSubmittedForReview] = useState(false);

  const textRef = useRef<HTMLTextAreaElement>(null);

  // Check if this is a draft version that can be edited
  // Non-DRAFT versions (PUBLISHED, PENDING_APPROVAL) are readonly
  const isDraft = !versionStatus || versionStatus === "DRAFT";
  const canEdit = isDraft && !!promptId;
  const canSubmitForReview = isDraft && !!promptId && !!onSubmitForReview;
  const isReadonly = readonly || !isDraft;

  useEffect(() => {
    if (typeof value === "string") setInputValue(value);
    setHasUnsavedChanges(false);
  }, [value, modalOpen]);

  useEffect(() => {
    if (!modalOpen) {
      onCloseModal?.();
      setShowReviewDialog(false);
      setReviewComment("");
    }
  }, [modalOpen]);

  // Track previous submitting state to detect when submission completes
  const wasSubmittingRef = useRef(false);
  useEffect(() => {
    // If we were submitting and now we're not, submission completed - close dialog
    if (wasSubmittingRef.current && !isSubmittingForReview && showReviewDialog) {
      setShowReviewDialog(false);
      setReviewComment("");
      setHasSubmittedForReview(true); // Mark as submitted to disable button
    }
    wasSubmittingRef.current = isSubmittingForReview ?? false;
  }, [isSubmittingForReview, showReviewDialog]);

  const handleSave = () => {
    setValue(inputValue);
    setHasUnsavedChanges(false);
  };

  const handleDiscardChanges = () => {
    setInputValue(value);
    setHasUnsavedChanges(false);
    setModalOpen(false);
  };

  const handleSubmitForReview = () => {
    // Save first if there are unsaved changes
    if (hasUnsavedChanges && !isReadonly) {
      handleSave();
    }
    // Also save to library before submitting
    if (onSaveVersion) {
      onSaveVersion(inputValue);
    }
    // Call submit - dialog will close when isSubmittingForReview becomes false
    onSubmitForReview?.(reviewComment);
  };

  // Prevent ESC key from closing the modal when there are unsaved changes
  const handleEscapeKeyDown = (e: KeyboardEvent) => {
    if (hasUnsavedChanges) {
      e.preventDefault();
      e.stopPropagation();
    }
  };

  return (
    <>
      <BaseModal
        onChangeOpenModal={() => { }}
        open={modalOpen}
        setOpen={setModalOpen}
        size="x-large"
        type="modal"
        onEscapeKeyDown={handleEscapeKeyDown}
      >
        <BaseModal.Trigger disable={disabled} asChild>
          {children}
        </BaseModal.Trigger>
        <BaseModal.Header>
          <div className="flex w-full items-start gap-3">
            <div className="flex mt-2 items-center">
              <IconComponent
                name={"FileText"}
                className="h-6 w-6 pr-1 text-primary"
                aria-hidden="true"
              />
              <span className="pl-2" data-testid="modal-title">
                {TEXT_DIALOG_TITLE}
              </span>
              {/* Version info */}
              {promptVersion && (
                <span className="ml-4 text-xs text-muted-foreground">
                  v{promptVersion} {versionStatus && `(${versionStatus})`}
                </span>
              )}
            </div>
            {password !== undefined && (
              <div>
                <button
                  onClick={() => {
                    if (changeVisibility) changeVisibility();
                  }}
                >
                  <IconComponent
                    name={password ? "Eye" : "EyeOff"}
                    className="h-6 w-6 cursor-pointer text-primary"
                  />
                </button>
              </div>
            )}
          </div>
        </BaseModal.Header>
        <BaseModal.Content overflowHidden>
          <div className={classNames("flex h-full w-full rounded-lg border")}>
            <Textarea
              password={password}
              ref={textRef}
              className="form-input h-full w-full resize-none overflow-auto rounded-lg focus-visible:ring-0"
              value={inputValue}
              onChange={(event) => {
                setInputValue(event.target.value);
                setHasUnsavedChanges(true);
              }}
              placeholder={EDIT_TEXT_PLACEHOLDER}
              onKeyDown={(e) => {
                handleKeyDown(e, value, "");
              }}
              readOnly={isReadonly}
              id={"text-area-modal"}
              data-testid={"text-area-modal"}
            />
          </div>
        </BaseModal.Content>
        <BaseModal.Footer>
          <div className="flex w-full shrink-0 items-center justify-between gap-2">
            {/* Left side - Genesis Prompt specific buttons */}
            <div className="flex items-center gap-2">
              {/* Submit for Review button - only for draft versions */}
              {canSubmitForReview && (
                <Button
                  data-testid="genericModalBtnSendForReview"
                  id="genericModalBtnSendForReview"
                  variant="default"
                  onClick={() => setShowReviewDialog(true)}
                  disabled={isSubmittingForReview || isSavingVersion || hasSubmittedForReview}
                  type="button"
                >
                  {hasSubmittedForReview ? "Submitted" : "Submit For Review"}
                </Button>
              )}
            </div>

            {/* Right side - Standard modal buttons */}
            <div className="flex items-center gap-2 ml-auto">
              {isReadonly ? (
                // For readonly versions (PUBLISHED, PENDING), just show Close button
                <Button
                  data-testid="genericModalBtnClose"
                  id="genericModalBtnClose"
                  variant="outline"
                  onClick={() => setModalOpen(false)}
                  type="button"
                >
                  Close
                </Button>
              ) : (
                // For DRAFT versions, show Discard and Finish Editing buttons
                <>
                  <Button
                    data-testid="genericModalBtnDiscardChanges"
                    id="genericModalBtnDiscardChanges"
                    variant="outline"
                    onClick={handleDiscardChanges}
                    type="button"
                  >
                    Discard Changes
                  </Button>
                  <Button
                    data-testid="genericModalBtnSave"
                    id="genericModalBtnSave"
                    disabled={!hasUnsavedChanges || isSavingVersion}
                    onClick={() => {
                      // Save locally first
                      handleSave();
                      // Save to the Prompt Library, close modal on success
                      if (canEdit && onSaveVersion) {
                        onSaveVersion(inputValue, () => {
                          setModalOpen(false);
                        });
                      } else {
                        // No library save needed, close immediately
                        setModalOpen(false);
                      }
                    }}
                    type="button"
                  >
                    {isSavingVersion ? "Saving..." : "Finish Editing"}
                  </Button>
                </>
              )}
            </div>
          </div>
        </BaseModal.Footer>
      </BaseModal>

      {/* Submit for Review Confirmation Modal */}
      <Dialog
        open={showReviewDialog}
        onOpenChange={(open) => {
          // Prevent closing while submitting
          if (!open && isSubmittingForReview) return;
          setShowReviewDialog(open);
          if (!open) setReviewComment("");
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Submit for Review</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 mt-3">
            <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950">
              <IconComponent
                name="AlertTriangle"
                className="h-4 w-4 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0"
              />
              <div className="text-sm text-amber-800 dark:text-amber-200">
                Once submitted, this version cannot be edited. It will be sent for approval.
              </div>
            </div>
            <Textarea
              value={reviewComment}
              onChange={(e) => setReviewComment(e.target.value)}
              placeholder="Add a comment for the reviewer (optional)"
              className="min-h-[80px] resize-none"
              disabled={isSubmittingForReview}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowReviewDialog(false);
                setReviewComment("");
              }}
              disabled={isSubmittingForReview}
              type="button"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSubmitForReview}
              disabled={isSubmittingForReview}
              type="button"
            >
              {isSubmittingForReview ? "Submitting..." : "Confirm & Submit"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
