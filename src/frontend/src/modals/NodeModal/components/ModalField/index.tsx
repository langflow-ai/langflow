import { useContext, useState } from "react";
import { TabsContext } from "../../../../contexts/tabsContext";
import InputListComponent from "../../../../components/inputListComponent";
import Dropdown from "../../../../components/dropdownComponent";
import TextAreaComponent from "../../../../components/textAreaComponent";
import InputComponent from "../../../../components/inputComponent";
import ToggleComponent from "../../../../components/toggleComponent";
import FloatComponent from "../../../../components/floatComponent";
import IntComponent from "../../../../components/intComponent";
import InputFileComponent from "../../../../components/inputFileComponent";
import PromptAreaComponent from "../../../../components/promptComponent";
import CodeAreaComponent from "../../../../components/codeAreaComponent";

export default function ModalField({ data, title, required, id, name, type }) {
	const { save } = useContext(TabsContext);
	const [enabled, setEnabled] = useState(
		data.node.template[name]?.value ?? false
	);

	return (
		<div className="flex my-3 flex-row w-full whitespace-nowrap items-center">
			<span className="mx-2">{title}</span>
			{type === "str" && !data.node.template[name].options ? (
				<div className="w-full">
					{data.node.template[name].list ? (
						<InputListComponent
							disabled={false}
							value={
								!data.node.template[name].value ||
								data.node.template[name].value === ""
									? [""]
									: data.node.template[name].value
							}
							onChange={(t: string[]) => {
								data.node.template[name].value = t;
								save();
							}}
						/>
					) : data.node.template[name].multiline ? (
						<TextAreaComponent
							disabled={false}
							value={data.node.template[name].value ?? ""}
							onChange={(t: string) => {
								data.node.template[name].value = t;
								save();
							}}
						/>
					) : (
						<InputComponent
							disabled={false}
							password={data.node.template[name].password ?? false}
							value={data.node.template[name].value ?? ""}
							onChange={(t) => {
								data.node.template[name].value = t;
								save();
							}}
						/>
					)}
				</div>
			) : type === "bool" ? (
				<div className="ml-auto">
					{" "}
					<ToggleComponent
						disabled={false}
						enabled={enabled}
						setEnabled={(t) => {
							data.node.template[name].value = t;
							setEnabled(t);
							save();
						}}
					/>
				</div>
			) : type === "float" ? (
				<div className="w-full">
					<FloatComponent
						disabled={false}
						value={data.node.template[name].value ?? ""}
						onChange={(t) => {
							data.node.template[name].value = t;
							save();
						}}
					/>
				</div>
			) : type === "str" && data.node.template[name].options ? (
				<div className="w-full">
					<Dropdown
						options={data.node.template[name].options}
						onSelect={(newValue) => (data.node.template[name].value = newValue)}
						value={data.node.template[name].value ?? "Choose an option"}
					></Dropdown>
				</div>
			) : type === "int" ? (
				<div className="w-full">
					<IntComponent
						disabled={false}
						value={data.node.template[name].value ?? ""}
						onChange={(t) => {
							data.node.template[name].value = t;
							save();
						}}
					/>
				</div>
			) : type === "file" ? (
				<div className="w-full">
				<InputFileComponent
					disabled={false}
					value={data.node.template[name].value ?? ""}
					onChange={(t: string) => {
						data.node.template[name].value = t;
					}}
					fileTypes={data.node.template[name].fileTypes}
					suffixes={data.node.template[name].suffixes}
					onFileChange={(t: string) => {
						data.node.template[name].content = t;
						save();
					}}
				></InputFileComponent>
				</div>
			) : type === "prompt" ? (
				<div className="w-full">
				<PromptAreaComponent
					disabled={false}
					value={data.node.template[name].value ?? ""}
					onChange={(t: string) => {
						data.node.template[name].value = t;
						save();
					}}
				/>
				</div>
			) : type === "code" ? (
				<div className="w-full">
				<CodeAreaComponent
					disabled={false}
					value={data.node.template[name].value ?? ""}
					onChange={(t: string) => {
						data.node.template[name].value = t;
						save();
					}}
				/>
				</div>
			) : (
				<div>{type}</div>
			)}
		</div>
	);
}
