"use client";
import {
  AnimatePresence,
  motion,
  MotionConfig,
  type Transition,
  type Variant,
  type Variants,
} from "framer-motion";
import * as React from "react";
import {
  createContext,
  memo,
  useCallback,
  useContext,
  useId,
  useMemo,
} from "react";
import { cn } from "../../utils/utils";

type DisclosureContextType = {
  open: boolean;
  toggle: () => void;
  variants?: { expanded: Variant; collapsed: Variant };
};

const DisclosureContext = createContext<DisclosureContextType | undefined>(
  undefined,
);

type DisclosureProviderProps = {
  children: React.ReactNode;
  open: boolean;
  onOpenChange?: (open: boolean) => void;
  variants?: { expanded: Variant; collapsed: Variant };
};

const DisclosureProvider = memo(function DisclosureProvider({
  children,
  open: openProp,
  onOpenChange,
  variants,
}: DisclosureProviderProps) {
  const toggle = useCallback(() => {
    if (onOpenChange) {
      onOpenChange(!openProp);
    }
  }, [onOpenChange, openProp]);

  const contextValue = useMemo(
    () => ({
      open: openProp,
      toggle,
      variants,
    }),
    [openProp, toggle, variants],
  );

  return (
    <DisclosureContext.Provider value={contextValue}>
      {children}
    </DisclosureContext.Provider>
  );
});

function useDisclosure() {
  const context = useContext(DisclosureContext);
  if (!context) {
    throw new Error("useDisclosure must be used within a DisclosureProvider");
  }
  return context;
}

type DisclosureProps = {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
  className?: string;
  variants?: { expanded: Variant; collapsed: Variant };
  transition?: Transition;
};

export const Disclosure = memo(function Disclosure({
  open: openProp = false,
  onOpenChange,
  children,
  className,
  transition,
  variants,
}: DisclosureProps) {
  const childrenArray = React.Children.toArray(children);

  return (
    <MotionConfig transition={transition}>
      <div className={className}>
        <DisclosureProvider
          open={openProp}
          onOpenChange={onOpenChange}
          variants={variants}
        >
          {childrenArray[0]}
          {childrenArray[1]}
        </DisclosureProvider>
      </div>
    </MotionConfig>
  );
});

const DisclosureTrigger = memo(function DisclosureTrigger({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const { toggle, open } = useDisclosure();

  const handleKeyDown = useCallback(
    (e: { key: string; preventDefault: () => void }) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggle();
      }
    },
    [toggle],
  );

  const childProps = useMemo(
    () => ({
      onClick: toggle,
      role: "button",
      "aria-expanded": open,
      tabIndex: 0,
      onKeyDown: handleKeyDown,
    }),
    [toggle, open, handleKeyDown],
  );

  return (
    <>
      {React.Children.map(children, (child) => {
        if (!React.isValidElement(child)) return child;

        return React.cloneElement(child, {
          ...childProps,
          className: cn(className, child.props.className),
          ...child.props,
        });
      })}
    </>
  );
});

const BASE_VARIANTS: Variants = {
  expanded: {
    height: "auto",
    opacity: 1,
  },
  collapsed: {
    height: 0,
    opacity: 0,
  },
};

const DisclosureContent = memo(function DisclosureContent({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const { open, variants } = useDisclosure();
  const uniqueId = useId();

  const combinedVariants = useMemo(
    () => ({
      expanded: { ...BASE_VARIANTS.expanded, ...variants?.expanded },
      collapsed: { ...BASE_VARIANTS.collapsed, ...variants?.collapsed },
    }),
    [variants],
  );

  return (
    <div className={cn("overflow-hidden", className)}>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={uniqueId}
            initial="collapsed"
            animate="expanded"
            exit="collapsed"
            variants={combinedVariants}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
});

export { DisclosureContent, DisclosureTrigger };

export default {
  Disclosure,
  DisclosureProvider,
  DisclosureTrigger,
  DisclosureContent,
};
