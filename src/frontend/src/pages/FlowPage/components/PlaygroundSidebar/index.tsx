import {
	SimpleSidebar,
	SimpleSidebarContent,
	SimpleSidebarHeader,
	useSimpleSidebar,
} from "@/components/ui/simple-sidebar";
import IconComponent from "../../../../components/common/genericIconComponent";
import { Button } from "../../../../components/ui/button";
import { PlaygroundComponent } from "@/components/core/playgroundComponent/playground-component";

export function PlaygroundSidebar() {
	const { setOpen } = useSimpleSidebar();

	return (
		<SimpleSidebar side="right" className="noflow select-none border-l">
			<SimpleSidebarHeader className=" p-0 overflow-hidden">
				<div className="flex items-center justify-between gap-2 px-4 py-2">
					<div className="flex items-center gap-2">
						<div className="truncate text-sm font-medium text-secondary-foreground">
							Flow run{" "}
							{new Date().toLocaleDateString("en-US", {
								month: "2-digit",
								day: "2-digit",
							})}{" "}
							{new Date().toLocaleTimeString("en-US", { hour12: false })}
						</div>
					</div>
					<div className="flex items-center gap-1">
						<Button
							variant="ghost"
							size="icon"
							className="flex h-8 items-center gap-2 text-muted-foreground"
						>
							<IconComponent name="Plus" className="h-4 w-4" />
						</Button>
						<Button
							variant="ghost"
							size="icon"
							className="flex h-8 items-center gap-2 text-muted-foreground"
						>
							<IconComponent name="History" className="h-4 w-4" />
						</Button>
						<Button
							variant="ghost"
							size="icon"
							className="flex h-8 items-center gap-2 text-muted-foreground"
						>
							<IconComponent name="ExternalLink" className="h-4 w-4" />
						</Button>
						<Button
							variant="ghost"
							size="iconMd"
							className="flex h-8 items-center gap-2 text-muted-foreground"
						>
							<IconComponent name="MoreHorizontal" className="h-4 w-4" />
						</Button>
						<Button
							variant="ghost"
							size="iconMd"
							className="flex h-8 items-center gap-2 text-muted-foreground"
							onClick={() => setOpen(false)}
						>
							<IconComponent name="X" className="h-4 w-4" />
						</Button>
					</div>
				</div>
			</SimpleSidebarHeader>

			<SimpleSidebarContent className="p-0">
				<div className="flex h-full w-full bg-background">
					<PlaygroundComponent />
				</div>
			</SimpleSidebarContent>
		</SimpleSidebar>
	);
}
