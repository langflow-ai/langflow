import { DialogClose } from "@radix-ui/react-dialog";
import * as Form from "@radix-ui/react-form";
import React, { type ReactNode, useEffect } from "react";
import { Button } from "../../components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogContentWithouFixed,
	DialogDescription,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "../../components/ui/dialog";
import {
	Dialog as Modal,
	DialogContent as ModalContent,
} from "../../components/ui/dialog-with-no-close";
import type { modalHeaderType } from "../../types/components";
import { cn } from "../../utils/utils";
import { switchCaseModalSize } from "./helpers/switch-case-size";

type ContentProps = {
	children: ReactNode;
	overflowHidden?: boolean;
	className?: string;
};
type HeaderProps = { children: ReactNode; description: string };
type FooterProps = { children: ReactNode };
type TriggerProps = {
	children: ReactNode;
	asChild?: boolean;
	disable?: boolean;
	className?: string;
};

const Content: React.FC<ContentProps> = ({
	children,
	overflowHidden,
	className,
}) => {
	return (
		<div
			className={cn(
				`flex flex-1 flex-col rounded-md transition-all duration-300`,
				overflowHidden ? "overflow-hidden" : "overflow-auto",
				className,
			)}
		>
			{children}
		</div>
	);
};
const Trigger: React.FC<TriggerProps> = ({
	children,
	asChild,
	disable,
	className,
}) => {
	return (
		<DialogTrigger
			className={asChild ? "" : cn("w-full", className)}
			hidden={children ? false : true}
			disabled={disable}
			asChild={asChild}
		>
			{children}
		</DialogTrigger>
	);
};

const Header: React.FC<{
	children: ReactNode;
	description?: string | JSX.Element | null;
	clampDescription?: number;
}> = ({
	children,
	description,
	clampDescription,
}: modalHeaderType): JSX.Element => {
	return (
		<DialogHeader>
			<DialogTitle className="line-clamp-1 flex items-center pb-0.5 text-base">
				{children}
			</DialogTitle>
			{description && (
				<DialogDescription
					className={`line-clamp-${clampDescription ?? 2} text-sm`}
				>
					{description}
				</DialogDescription>
			)}
		</DialogHeader>
	);
};

const Footer: React.FC<{
	children?: ReactNode;
	submit?: {
		label: string;
		icon?: ReactNode;
		loading?: boolean;
		disabled?: boolean;
		dataTestId?: string;
		onClick?: () => void;
	};
	close?: boolean;
	centered?: boolean;
	className?: string;
}> = ({ children, submit, close, centered, className }) => {
	return (
		<div
			className={cn(
				centered
					? "flex flex-shrink-0 justify-center"
					: "flex flex-shrink-0 flex-row-reverse",
				className,
			)}
		>
			{submit ? (
				<div className="flex w-full items-center justify-between">
					{children ?? <div />}
					<div className="flex items-center gap-3">
						<DialogClose asChild>
							<Button
								variant="outline"
								type="button"
								data-testid="btn-cancel-modal"
							>
								Cancel
							</Button>
						</DialogClose>
						<Button
							data-testid={submit.dataTestId}
							type={submit.onClick ? "button" : "submit"}
							onClick={submit.onClick}
							loading={submit.loading}
							disabled={submit.disabled}
						>
							{submit.icon && submit.icon}
							{submit.label}
						</Button>
					</div>
				</div>
			) : (
				<>{children && children}</>
			)}
			{close && (
				<DialogClose asChild>
					<Button data-testid="btn-close-modal" type="button">
						Close
					</Button>
				</DialogClose>
			)}
		</div>
	);
};
interface BaseModalProps {
	children:
		| [
				React.ReactElement<ContentProps>,
				React.ReactElement<HeaderProps>?,
				React.ReactElement<TriggerProps>?,
				React.ReactElement<FooterProps>?,
		  ]
		| React.ReactElement<ContentProps>;
	open?: boolean;
	setOpen?: (open: boolean) => void;
	size?:
		| "notice"
		| "x-small"
		| "retangular"
		| "smaller"
		| "small"
		| "small-update"
		| "small-query"
		| "medium"
		| "medium-tall"
		| "large"
		| "three-cards"
		| "large-thin"
		| "large-h-full"
		| "templates"
		| "small-h-full"
		| "medium-small-tall"
		| "medium-h-full"
		| "md-thin"
		| "sm-thin"
		| "smaller-h-full"
		| "medium-log"
		| "x-large"
		| "auth";
	className?: string;
	disable?: boolean;
	onChangeOpenModal?: (open?: boolean) => void;
	type?: "modal" | "dialog" | "full-screen";
	onSubmit?: () => void;
	onEscapeKeyDown?: (e: KeyboardEvent) => void;
	closeButtonClassName?: string;
	dialogContentWithouFixed?: boolean;
}
function BaseModal({
	className,
	open,
	setOpen,
	children,
	size = "large",
	onChangeOpenModal,
	type = "dialog",
	onSubmit,
	onEscapeKeyDown,
	closeButtonClassName,
	dialogContentWithouFixed = false,
}: BaseModalProps) {
	const headerChild = React.Children.toArray(children).find(
		(child) => (child as React.ReactElement).type === Header,
	);
	const triggerChild = React.Children.toArray(children).find(
		(child) => (child as React.ReactElement).type === Trigger,
	);
	const ContentChild = React.Children.toArray(children).find(
		(child) => (child as React.ReactElement).type === Content,
	);
	const ContentFooter = React.Children.toArray(children).find(
		(child) => (child as React.ReactElement).type === Footer,
	);

	const { minWidth, height } = switchCaseModalSize(size);

	useEffect(() => {
		if (onChangeOpenModal) {
			onChangeOpenModal(open);
		}
	}, [open]);

	const modalContent = (
		<>
			{headerChild && headerChild}
			{ContentChild}
			{ContentFooter && ContentFooter}
		</>
	);

	const contentClasses = cn(
		minWidth,
		height,
		"flex flex-col flex-1 overflow-hidden max-h-[98dvh]",
		className,
	);

	const formClasses = "flex flex-col flex-1 gap-6 overflow-hidden";

	//UPDATE COLORS AND STYLE CLASSSES
	return (
		<>
			{type === "modal" ? (
				<Modal open={open} onOpenChange={setOpen}>
					{triggerChild}
					<ModalContent className={contentClasses}>{modalContent}</ModalContent>
				</Modal>
			) : type === "full-screen" ? (
				<div className="min-h-full w-full flex-1 overflow-hidden">
					{modalContent}
				</div>
			) : (
				<Dialog open={open} onOpenChange={setOpen}>
					{triggerChild}
					{dialogContentWithouFixed ? (
						<DialogContentWithouFixed
							onClick={(e) => e.stopPropagation()}
							onOpenAutoFocus={(event) => event.preventDefault()}
							onEscapeKeyDown={onEscapeKeyDown}
							className={contentClasses}
							closeButtonClassName={closeButtonClassName}
						>
							{onSubmit ? (
								<Form.Root
									onSubmit={(event) => {
										event.preventDefault();
										onSubmit();
									}}
									className={formClasses}
								>
									{modalContent}
								</Form.Root>
							) : (
								modalContent
							)}
						</DialogContentWithouFixed>
					) : (
						<DialogContent
							onClick={(e) => e.stopPropagation()}
							onOpenAutoFocus={(event) => event.preventDefault()}
							onEscapeKeyDown={onEscapeKeyDown}
							className={contentClasses}
							closeButtonClassName={closeButtonClassName}
						>
							{onSubmit ? (
								<Form.Root
									onSubmit={(event) => {
										event.preventDefault();
										onSubmit();
									}}
									className={formClasses}
								>
									{modalContent}
								</Form.Root>
							) : (
								modalContent
							)}
						</DialogContent>
					)}
				</Dialog>
			)}
		</>
	);
}

BaseModal.Content = Content;
BaseModal.Header = Header;
BaseModal.Trigger = Trigger;
BaseModal.Footer = Footer;
export default BaseModal;
