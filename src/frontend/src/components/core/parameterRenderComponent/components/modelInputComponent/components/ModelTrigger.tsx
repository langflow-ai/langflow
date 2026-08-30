import { RefObject } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/utils/utils";
import { ModelOption, SelectedModel } from "../types";

/**
 * The trigger collapses into a single "Setup Provider" call to action — which
 * already opens the provider manager, so no extra affordance belongs next to it.
 */
export const isSetupProviderState = ({
  hasEnabledProviders,
  showEmptyState,
  optionCount,
}: {
  hasEnabledProviders: boolean;
  showEmptyState: boolean;
  optionCount: number;
}) => !hasEnabledProviders && !showEmptyState && optionCount === 0;

interface ModelTriggerProps {
  open: boolean;
  disabled: boolean;
  options: ModelOption[];
  selectedModel: SelectedModel | null;
  placeholder?: string;
  hasEnabledProviders: boolean;
  onOpenManageProviders: () => void;
  id: string;
  refButton: RefObject<HTMLButtonElement | null>;
  showEmptyState?: boolean;
  "aria-label"?: string;
  ariaLabelledBy?: string;
  ariaDescribedBy?: string;
  ariaInvalid?: boolean;
}

const ModelTrigger = ({
  open,
  disabled,
  options,
  selectedModel,
  placeholder = "Setup Provider",
  hasEnabledProviders,
  onOpenManageProviders,
  id,
  refButton,
  showEmptyState = false,
  "aria-label": ariaLabel,
  ariaLabelledBy,
  ariaDescribedBy,
  ariaInvalid,
}: ModelTriggerProps) => {
  const { t } = useTranslation();
  const renderSelectedIcon = () => {
    if (disabled || options.length === 0) {
      return null;
    }

    return selectedModel?.icon ? (
      <ForwardedIconComponent
        name={selectedModel.icon || "Bot"}
        className="h-4 w-4 flex-shrink-0"
      />
    ) : null;
  };

  // Check if we're in empty state mode (showEmptyState=true and no options)
  const isEmptyStateMode = showEmptyState && options.length === 0;
  // The saved model is no longer offered to this user (restricted by an
  // administrator or removed from the catalog). Keep naming it, but say so.
  const isUnavailable = selectedModel?.metadata?.unavailable === true;

  // A selected-but-unavailable model outranks the setup-provider call to
  // action: replacing it with "Setup Provider" would hide both the saved
  // selection and the reason it cannot be used (the footer still offers
  // provider management).
  if (
    !isUnavailable &&
    isSetupProviderState({
      hasEnabledProviders,
      showEmptyState,
      optionCount: options.length,
    })
  ) {
    // Unlike the combobox below — whose visible text is its *value*, so the
    // field label alone is the right accessible name — this branch is a plain
    // button whose visible text is its label. WCAG 2.5.3 (Label in Name)
    // requires that text to be part of the accessible name, so the field label
    // is composed after it rather than replacing it: speech input matches what
    // the user reads ("click Setup Provider"), and the field label still tells
    // a screen reader user which field the CTA belongs to.
    const setupProviderTextId = `${id}-setup-provider-label`;
    const setupProviderText =
      placeholder === "Setup Provider" ? t("model.setupProvider") : placeholder;

    return (
      <Button
        variant="outline"
        size="xs"
        className="dropdown-component-false-outline w-full justify-start gap-2 py-2 font-normal"
        onClick={onOpenManageProviders}
        aria-label={
          !ariaLabelledBy && ariaLabel
            ? `${setupProviderText}, ${ariaLabel}`
            : undefined
        }
        aria-labelledby={
          ariaLabelledBy
            ? `${setupProviderTextId} ${ariaLabelledBy}`
            : undefined
        }
        aria-describedby={ariaDescribedBy}
      >
        <ForwardedIconComponent
          name="BrainCircuit"
          className="h-4 w-4 flex-shrink-0 text-muted-foreground"
        />
        <div
          id={setupProviderTextId}
          className="text-[13px] text-muted-foreground"
        >
          {setupProviderText}
        </div>
      </Button>
    );
  }

  return (
    <div className="flex w-full flex-col">
      <PopoverTrigger asChild>
        <Button
          id={id}
          disabled={disabled}
          variant="primary"
          size="xs"
          role="combobox"
          ref={refButton}
          aria-expanded={open}
          aria-label={!ariaLabelledBy ? ariaLabel : undefined}
          aria-labelledby={ariaLabelledBy}
          aria-describedby={ariaDescribedBy}
          aria-invalid={ariaInvalid || undefined}
          data-testid={id}
          className={cn(
            "dropdown-component-false-outline py-2",
            "focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-2 w-full justify-between font-normal disabled:bg-muted disabled:text-muted-foreground",
          )}
        >
          <span
            className="flex w-full items-center gap-2 overflow-hidden"
            data-testid={`value-dropdown-${id}`}
          >
            {renderSelectedIcon()}
            <span className="truncate">
              {disabled ? (
                t("component.receivingInput")
              ) : isEmptyStateMode ? (
                <div className="truncate text-muted-foreground">
                  {t("model.noModelsEnabled")}
                </div>
              ) : (
                <div
                  className={cn(
                    "truncate",
                    !selectedModel?.name && "text-muted-foreground",
                  )}
                >
                  {selectedModel?.name || t("model.selectModel")}
                </div>
              )}
            </span>
            {!disabled && isUnavailable ? (
              <span
                data-testid={`${id}-unavailable`}
                title={t("model.unavailableTitle")}
                aria-label={t("model.unavailableTitle")}
                className="inline-flex shrink-0 items-center gap-1 text-[11px] text-accent-amber-foreground"
              >
                <ForwardedIconComponent
                  name="TriangleAlert"
                  className="h-3.5 w-3.5"
                />
                {t("model.unavailable")}
              </span>
            ) : null}
          </span>
          <ForwardedIconComponent
            name={disabled ? "Lock" : "ChevronsUpDown"}
            className={cn(
              "ml-2 h-4 w-4 shrink-0 text-foreground",
              disabled
                ? "text-placeholder-foreground hover:text-placeholder-foreground"
                : "hover:text-foreground",
            )}
          />
        </Button>
      </PopoverTrigger>
    </div>
  );
};

export default ModelTrigger;
