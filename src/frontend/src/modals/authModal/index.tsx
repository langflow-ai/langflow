import { useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Separator } from "@/components/ui/separator";
import type { AuthSettingsType } from "@/types/mcp";
import { AUTH_METHODS_ARRAY } from "@/utils/mcpUtils";
import BaseModal from "../baseModal";

interface AuthModalProps {
	open: boolean;
	setOpen: (open: boolean) => void;
	authSettings?: AuthSettingsType;
	onSave: (authSettings: AuthSettingsType) => void;
}

const AuthModal = ({ open, setOpen, authSettings, onSave }: AuthModalProps) => {
	const [authType, setAuthType] = useState<string>(
		authSettings?.auth_type || "none",
	);
	const [authFields, setAuthFields] = useState<{
		apiKey?: string;
		iamEndpoint?: string;
		username?: string;
		password?: string;
		bearerToken?: string;
		oauthHost?: string;
		oauthPort?: string;
		oauthServerUrl?: string;
		oauthCallbackPath?: string;
		oauthClientId?: string;
		oauthClientSecret?: string;
		oauthAuthUrl?: string;
		oauthTokenUrl?: string;
		oauthMcpScope?: string;
		oauthProviderScope?: string;
	}>({
		apiKey: authSettings?.api_key || "",
		iamEndpoint: authSettings?.iam_endpoint || "",
		username: authSettings?.username || "",
		password: authSettings?.password || "",
		bearerToken: authSettings?.bearer_token || "",
		oauthHost: authSettings?.oauth_host || "",
		oauthPort: authSettings?.oauth_port || "",
		oauthServerUrl: authSettings?.oauth_server_url || "",
		oauthCallbackPath: authSettings?.oauth_callback_path || "",
		oauthClientId: authSettings?.oauth_client_id || "",
		oauthClientSecret: authSettings?.oauth_client_secret || "",
		oauthAuthUrl: authSettings?.oauth_auth_url || "",
		oauthTokenUrl: authSettings?.oauth_token_url || "",
		oauthMcpScope: authSettings?.oauth_mcp_scope || "",
		oauthProviderScope: authSettings?.oauth_provider_scope || "",
	});

	// Update auth state when authSettings prop changes
	useEffect(() => {
		if (authSettings) {
			setAuthType(authSettings.auth_type || "none");
			setAuthFields({
				apiKey: authSettings.api_key || "",
				iamEndpoint: authSettings.iam_endpoint || "",
				username: authSettings.username || "",
				password: authSettings.password || "",
				bearerToken: authSettings.bearer_token || "",
				oauthHost: authSettings.oauth_host || "",
				oauthPort: authSettings.oauth_port || "",
				oauthServerUrl: authSettings.oauth_server_url || "",
				oauthCallbackPath: authSettings.oauth_callback_path || "",
				oauthClientId: authSettings.oauth_client_id || "",
				oauthClientSecret: authSettings.oauth_client_secret || "",
				oauthAuthUrl: authSettings.oauth_auth_url || "",
				oauthTokenUrl: authSettings.oauth_token_url || "",
				oauthMcpScope: authSettings.oauth_mcp_scope || "",
				oauthProviderScope: authSettings.oauth_provider_scope || "",
			});
		}
	}, [authSettings]);

	const handleAuthTypeChange = (value: string) => {
		setAuthType(value);
		setAuthFields({});
	};

	const handleAuthFieldChange = (field: string, value: string) => {
		setAuthFields((prev) => ({
			...prev,
			[field]: value,
		}));
	};

	const handleSave = () => {
		const authSettingsToSave: AuthSettingsType = {
			auth_type: authType,
			...(authType === "apikey" && { api_key: authFields.apiKey }),
			...(authType === "basic" && {
				username: authFields.username,
				password: authFields.password,
			}),
			...(authType === "iam" && {
				iam_endpoint: authFields.iamEndpoint,
				api_key: authFields.apiKey,
			}),
			...(authType === "bearer" && { bearer_token: authFields.bearerToken }),
			...(authType === "oauth" && {
				oauth_host: authFields.oauthHost,
				oauth_port: authFields.oauthPort,
				oauth_server_url: authFields.oauthServerUrl,
				oauth_callback_path: authFields.oauthCallbackPath,
				oauth_client_id: authFields.oauthClientId,
				oauth_client_secret: authFields.oauthClientSecret,
				oauth_auth_url: authFields.oauthAuthUrl,
				oauth_token_url: authFields.oauthTokenUrl,
				oauth_mcp_scope: authFields.oauthMcpScope,
				oauth_provider_scope: authFields.oauthProviderScope,
			}),
		};

		onSave(authSettingsToSave);
		setOpen(false);
	};

	return (
		<BaseModal
			open={open}
			setOpen={setOpen}
			size="auth"
			className="p-0 gap-0 flex flex-col"
		>
			<BaseModal.Content className="h-full " overflowHidden>
				<div className="flex items-center w-full p-4 gap-2 text-sm font-medium">
					<ForwardedIconComponent
						name="Fingerprint"
						className="h-4 w-4 shrink-0"
					/>
					Configure MCP Server Authentication
				</div>
				<div className="flex h-full p-0 border-t rounded-none">
					{/* Left column - Radio buttons */}
					<div className="flex flex-col p-4 gap-2 flex-1 items-start min-h-[400px]">
						<span className="text-mmd font-medium text-muted-foreground">
							Auth type
						</span>
						<RadioGroup value={authType} onValueChange={handleAuthTypeChange}>
							{AUTH_METHODS_ARRAY.map((option) => (
								<div key={option.id} className="flex items-center space-x-2">
									<RadioGroupItem value={option.id} id={option.id} />
									<Label
										htmlFor={option.id}
										className="!text-mmd font-normal cursor-pointer flex items-center gap-3"
									>
										{option.label}
										{option.id === "none" && authType === "none" && (
											<span className="text-accent-amber-foreground flex gap-1.5 text-xs items-center">
												<ForwardedIconComponent
													name="AlertTriangle"
													className="h-3.5 w-3.5 shrink-0"
												/>
												Public endpoint - no auth. Use only in dev or trusted
												envs.
											</span>
										)}
									</Label>
								</div>
							))}
						</RadioGroup>
					</div>
					<div>
						{authType !== "none" && <Separator orientation="vertical" />}
					</div>
					{/* Right column - Input fields */}
					{authType !== "none" && (
						<div className="w-[70%] flex flex-col overflow-y-auto h-fit max-h-[400px] p-4">
							{authType === "apikey" && (
								<div className="flex flex-col items-start gap-2">
									<Label htmlFor="api-key" className="!text-mmd font-medium">
										API Key Value
									</Label>
									<Input
										id="api-key"
										type="password"
										placeholder="Enter API Key"
										value={authFields.apiKey || ""}
										onChange={(e) =>
											handleAuthFieldChange("apiKey", e.target.value)
										}
									/>
								</div>
							)}

							{authType === "basic" && (
								<div className="flex flex-col gap-4">
									<div className="flex flex-col gap-2">
										<Label htmlFor="username" className="!text-mmd font-medium">
											Username
										</Label>
										<Input
											id="username"
											type="text"
											placeholder="Enter Username"
											value={authFields.username || ""}
											onChange={(e) =>
												handleAuthFieldChange("username", e.target.value)
											}
										/>
									</div>
									<div className="flex flex-col gap-2">
										<Label htmlFor="password" className="!text-mmd font-medium">
											Password
										</Label>
										<Input
											id="password"
											type="password"
											placeholder="Enter Password"
											value={authFields.password || ""}
											onChange={(e) =>
												handleAuthFieldChange("password", e.target.value)
											}
										/>
									</div>
								</div>
							)}

							{authType === "bearer" && (
								<div className="flex flex-col gap-2">
									<Label
										htmlFor="bearer-token"
										className="!text-mmd font-medium"
									>
										Bearer Token
									</Label>
									<Input
										id="bearer-token"
										type="password"
										placeholder="Enter Bearer Token"
										value={authFields.bearerToken || ""}
										onChange={(e) =>
											handleAuthFieldChange("bearerToken", e.target.value)
										}
									/>
								</div>
							)}

							{authType === "iam" && (
								<div className="flex flex-col gap-4">
									<div className="flex flex-col gap-2">
										<Label
											htmlFor="iam-endpoint"
											className="!text-mmd font-medium"
										>
											IAM Endpoint
										</Label>
										<Input
											id="iam-endpoint"
											type="text"
											placeholder="Enter IAM Endpoint"
											value={authFields.iamEndpoint || ""}
											onChange={(e) =>
												handleAuthFieldChange("iamEndpoint", e.target.value)
											}
										/>
									</div>
									<div className="flex flex-col gap-2">
										<Label htmlFor="api-key" className="!text-mmd font-medium">
											API Key or Token
										</Label>
										<Input
											id="password"
											type="password"
											placeholder="Enter API Key or Token"
											value={authFields.apiKey || ""}
											onChange={(e) =>
												handleAuthFieldChange("apiKey", e.target.value)
											}
										/>
									</div>
								</div>
							)}

							{authType === "oauth" && (
								<div className="flex flex-col gap-4 h-full">
									<span className="text-mmd font-medium text-muted-foreground">
										OAuth settings
									</span>
									<div className="grid grid-cols-2 gap-3">
										<div className="flex flex-col gap-2">
											<Label
												htmlFor="oauth-host"
												className="!text-mmd font-medium"
											>
												Host
											</Label>
											<Input
												id="oauth-host"
												type="text"
												placeholder="localhost"
												value={authFields.oauthHost || ""}
												onChange={(e) =>
													handleAuthFieldChange("oauthHost", e.target.value)
												}
											/>
										</div>
										<div className="flex flex-col gap-2">
											<Label
												htmlFor="oauth-port"
												className="!text-mmd font-medium"
											>
												Port
											</Label>
											<Input
												id="oauth-port"
												type="text"
												placeholder="1234"
												value={authFields.oauthPort || ""}
												onChange={(e) =>
													handleAuthFieldChange("oauthPort", e.target.value)
												}
											/>
										</div>
									</div>
									<div className="flex flex-col gap-2">
										<Label
											htmlFor="oauth-server-url"
											className="!text-mmd font-medium"
										>
											Server URL
										</Label>
										<Input
											id="oauth-server-url"
											type="text"
											placeholder="http://localhost:1234"
											value={authFields.oauthServerUrl || ""}
											onChange={(e) =>
												handleAuthFieldChange("oauthServerUrl", e.target.value)
											}
										/>
									</div>
									<div className="flex flex-col gap-2">
										<Label
											htmlFor="oauth-callback-path"
											className="!text-mmd font-medium"
										>
											Callback Path
										</Label>
										<Input
											id="oauth-callback-path"
											type="text"
											placeholder="http://localhost:9000/auth/idaas/callback"
											value={authFields.oauthCallbackPath || ""}
											onChange={(e) =>
												handleAuthFieldChange(
													"oauthCallbackPath",
													e.target.value,
												)
											}
										/>
									</div>
									<div className="flex flex-col gap-2">
										<Label
											htmlFor="oauth-client-id"
											className="!text-mmd font-medium"
										>
											Client ID
										</Label>
										<Input
											id="oauth-client-id"
											type="text"
											placeholder="Enter Client ID"
											value={authFields.oauthClientId || ""}
											onChange={(e) =>
												handleAuthFieldChange("oauthClientId", e.target.value)
											}
										/>
									</div>
									<div className="flex flex-col gap-2">
										<Label
											htmlFor="oauth-client-secret"
											className="!text-mmd font-medium"
										>
											Client Secret
										</Label>
										<Input
											id="oauth-client-secret"
											type="password"
											placeholder="Enter Client Secret"
											value={authFields.oauthClientSecret || ""}
											onChange={(e) =>
												handleAuthFieldChange(
													"oauthClientSecret",
													e.target.value,
												)
											}
										/>
									</div>
									<div className="flex flex-col gap-2">
										<Label
											htmlFor="oauth-auth-url"
											className="!text-mmd font-medium"
										>
											Authorization URL
										</Label>
										<Input
											id="oauth-auth-url"
											type="text"
											value={authFields.oauthAuthUrl || ""}
											placeholder="http://localhost:1234/auth/idaas/authorize"
											onChange={(e) =>
												handleAuthFieldChange("oauthAuthUrl", e.target.value)
											}
										/>
									</div>
									<div className="flex flex-col gap-2">
										<Label
											htmlFor="oauth-token-url"
											className="!text-mmd font-medium"
										>
											Token URL
										</Label>
										<Input
											id="oauth-token-url"
											type="text"
											value={authFields.oauthTokenUrl || ""}
											placeholder="http://localhost:1234/auth/idaas/token"
											onChange={(e) =>
												handleAuthFieldChange("oauthTokenUrl", e.target.value)
											}
										/>
									</div>
									<div className="flex flex-col gap-2">
										<Label
											htmlFor="oauth-mcp-scope"
											className="!text-mmd font-medium"
										>
											MCP Scope
										</Label>
										<Input
											id="oauth-mcp-scope"
											type="text"
											placeholder="user"
											value={authFields.oauthMcpScope || ""}
											onChange={(e) =>
												handleAuthFieldChange("oauthMcpScope", e.target.value)
											}
										/>
									</div>
									<div className="flex flex-col gap-2">
										<Label
											htmlFor="oauth-provider-scope"
											className="!text-mmd font-medium"
										>
											Provider Scope
										</Label>
										<Input
											id="oauth-provider-scope"
											type="text"
											placeholder="openid"
											value={authFields.oauthProviderScope || ""}
											onChange={(e) =>
												handleAuthFieldChange(
													"oauthProviderScope",
													e.target.value,
												)
											}
										/>
									</div>
								</div>
							)}
						</div>
					)}
				</div>
			</BaseModal.Content>
			<BaseModal.Footer
				submit={{
					label: "Save",
					onClick: handleSave,
				}}
				className="p-4 border-t"
			/>
		</BaseModal>
	);
};

export default AuthModal;
