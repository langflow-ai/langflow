"use client";

import * as React from "react";
import { useHotkeys } from "react-hotkeys-hook";
import isWrappedWithClass from "../../pages/FlowPage/components/PageComponent/utils/is-wrapped-with-class";
import { cn } from "../../utils/utils";

const SIMPLE_SIDEBAR_WIDTH = "400px";

type SimpleSidebarContext = {
	open: boolean;
	setOpen: (open: boolean) => void;
	toggleSidebar: () => void;
};

const SimpleSidebarContext = React.createContext<SimpleSidebarContext | null>(
	null,
);

function useSimpleSidebar() {
	const context = React.useContext(SimpleSidebarContext);
	if (!context) {
		throw new Error(
			"useSimpleSidebar must be used within a SimpleSidebarProvider.",
		);
	}

	return context;
}

const SimpleSidebarProvider = React.forwardRef<
	HTMLDivElement,
	React.ComponentProps<"div"> & {
		defaultOpen?: boolean;
		open?: boolean;
		onOpenChange?: (open: boolean) => void;
		width?: string;
		shortcut?: string;
	}
>(
	(
		{
			defaultOpen = false,
			open: openProp,
			onOpenChange: setOpenProp,
			className,
			style,
			children,
			width = SIMPLE_SIDEBAR_WIDTH,
			shortcut,
			...props
		},
		ref,
	) => {
		// This is the internal state of the sidebar.
		// We use openProp and setOpenProp for control from outside the component.
		const [_open, _setOpen] = React.useState(defaultOpen);
		const open = openProp ?? _open;
		const setOpen = React.useCallback(
			(value: boolean | ((value: boolean) => boolean)) => {
				if (setOpenProp) {
					return setOpenProp?.(
						typeof value === "function" ? value(open) : value,
					);
				}

				_setOpen(value);
			},
			[setOpenProp, open],
		);

		// Helper to toggle the sidebar.
		const toggleSidebar = React.useCallback(() => {
			return setOpen((prev) => !prev);
		}, [setOpen]);

		const contextValue = React.useMemo<SimpleSidebarContext>(
			() => ({
				open,
				setOpen,
				toggleSidebar,
			}),
			[open, setOpen, toggleSidebar],
		);

		// Register hotkey if provided
		useHotkeys(
			shortcut ?? "",
			(e: KeyboardEvent) => {
				if (!shortcut) return;
				if (isWrappedWithClass(e, "noflow")) return;
				e.preventDefault();
				toggleSidebar();
			},
			{
				preventDefault: true,
				enabled: !!shortcut,
			},
		);

		return (
			<SimpleSidebarContext.Provider value={contextValue}>
				<div
					style={
						{
							"--simple-sidebar-width": width,
							...style,
						} as React.CSSProperties
					}
					className={cn(
						"group/simple-sidebar-wrapper flex h-full w-full text-foreground",
						className,
					)}
					data-open={open}
					ref={ref}
					{...props}
				>
					{children}
				</div>
			</SimpleSidebarContext.Provider>
		);
	},
);
SimpleSidebarProvider.displayName = "SimpleSidebarProvider";

const SimpleSidebar = React.forwardRef<
	HTMLDivElement,
	React.ComponentProps<"div"> & {
		side?: "left" | "right";
	}
>(({ side = "right", className, children, ...props }, ref) => {
	const { open } = useSimpleSidebar();

	return (
		<div
			ref={ref}
			className="relative block h-full flex-col"
			data-open={open}
			data-side={side}
		>
			{/* This is what handles the sidebar gap */}
			<div
				className={cn(
					"relative h-full w-[--simple-sidebar-width] bg-transparent transition-[width] duration-200 ease-linear",
					!open && "w-0",
				)}
			/>
			<div
				className={cn(
					"absolute inset-y-0 z-50 flex h-full transition-[left,right,width] duration-200 ease-linear",
					"w-[--simple-sidebar-width]",
					side === "left"
						? cn(
								"left-0",
								!open && "left-[calc(var(--simple-sidebar-width)*-1)]",
							)
						: cn(
								"right-0",
								!open && "right-[calc(var(--simple-sidebar-width)*-1)]",
							),
					className,
				)}
				{...props}
			>
				<div
					data-simple-sidebar="sidebar"
					className="flex h-full w-full flex-col bg-background"
				>
					{children}
				</div>
			</div>
		</div>
	);
});
SimpleSidebar.displayName = "SimpleSidebar";

const SimpleSidebarTrigger = React.forwardRef<
	HTMLButtonElement,
	React.ComponentProps<"button">
>(({ className, onClick, children, ...props }, ref) => {
	const { toggleSidebar } = useSimpleSidebar();

	const handleClick = React.useCallback(
		(event: React.MouseEvent<HTMLButtonElement>) => {
			onClick?.(event);
			toggleSidebar();
		},
		[onClick, toggleSidebar],
	);

	return (
		<button
			ref={ref}
			data-simple-sidebar="trigger"
			className={cn("outline-none", className)}
			onClick={handleClick}
			{...props}
		>
			{children}
		</button>
	);
});
SimpleSidebarTrigger.displayName = "SimpleSidebarTrigger";

const SimpleSidebarHeader = React.forwardRef<
	HTMLDivElement,
	React.ComponentProps<"div">
>(({ className, ...props }, ref) => {
	return (
		<div
			ref={ref}
			data-simple-sidebar="header"
			className={cn("flex flex-col gap-2 p-2", className)}
			{...props}
		/>
	);
});
SimpleSidebarHeader.displayName = "SimpleSidebarHeader";

const SimpleSidebarContent = React.forwardRef<
	HTMLDivElement,
	React.ComponentProps<"div">
>(({ className, ...props }, ref) => {
	return (
		<div
			ref={ref}
			data-simple-sidebar="content"
			className={cn(
				"flex min-h-0 flex-1 flex-col gap-2 overflow-auto",
				className,
			)}
			{...props}
		/>
	);
});
SimpleSidebarContent.displayName = "SimpleSidebarContent";

export {
	SimpleSidebar,
	SimpleSidebarContent,
	SimpleSidebarHeader,
	SimpleSidebarProvider,
	SimpleSidebarTrigger,
	useSimpleSidebar,
};
