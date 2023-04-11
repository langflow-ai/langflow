import { useContext } from "react";
import { TabsContext } from "../../../../contexts/tabsContext";
import InputListComponent from "../../../../components/inputListComponent";
import Dropdown from "../../../../components/dropdownComponent";
import TextAreaComponent from "../../../../components/textAreaComponent";
import InputComponent from "../../../../components/inputComponent";

export default function ModalField({ data, title, required, id, name, type }) {
	const { save } = useContext(TabsContext);
	console.log(name);
	console.log(data.node.template[name].options);

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
			) : (
				<div>{name}</div>
			)}
		</div>
	);
}
