import { useContext, useState } from "react";
import { TabsContext } from "../../../../contexts/tabsContext";
import InputListComponent from "../../../../components/inputListComponent";
import Dropdown from "../../../../components/dropdownComponent";
import TextAreaComponent from "../../../../components/textAreaComponent";
import InputComponent from "../../../../components/inputComponent";
import ToggleComponent from "../../../../components/toggleComponent";
import FloatComponent from "../../../../components/floatComponent";

export default function ModalField({ data, title, required, id, name, type }) {
	const { save } = useContext(TabsContext);
	const [enabled, setEnabled] = useState(
		data.node.template[name]?.value ?? false
	);

	return (
		<div>
			{type === "str" && !data.node.template[name].options ? (
				<div>
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
				<div>
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
				<FloatComponent
					disabled={false}
					value={data.node.template[name].value ?? ""}
					onChange={(t) => {
						data.node.template[name].value = t;
						save();
					}}
				/>
			) : type === "str" && data.node.template[name].options ? (
				<Dropdown
					options={data.node.template[name].options}
					onSelect={(newValue) => (data.node.template[name].value = newValue)}
					value={data.node.template[name].value ?? "Choose an option"}
				></Dropdown>
			) : (
				<div>{name}</div>
			)}
		</div>
	);
}
