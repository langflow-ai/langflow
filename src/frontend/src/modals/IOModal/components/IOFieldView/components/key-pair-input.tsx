import _ from "lodash";
import { useCallback, useEffect, useState } from "react";
import IconComponent from "../../../../../components/common/genericIconComponent";
import { Input } from "../../../../../components/ui/input";
import { classNames } from "../../../../../utils/utils";

export type IOKeyPairInputProps = {
	value: any;
	onChange: (value: any) => void;
	duplicateKey: boolean;
	isList: boolean;
	isInputField?: boolean;
	testId?: string;
};

const IOKeyPairInput = ({
	value,
	onChange,
	duplicateKey,
	isList = true,
	isInputField,
	testId,
}: IOKeyPairInputProps) => {
	const checkValueType = useCallback((value) => {
		return Array.isArray(value) ? value : [value];
	}, []);

	const [currentData, setCurrentData] = useState<any[]>(() => {
		return !value || value?.length === 0 ? [{ "": "" }] : checkValueType(value);
	});

	// Update internal state when external value changes
	useEffect(() => {
		const newData =
			!value || value?.length === 0 ? [{ "": "" }] : checkValueType(value);
		setCurrentData(newData);
	}, [value, checkValueType]);

	const handleChangeKey = (event, objIndex) => {
		const oldKey = Object.keys(currentData[objIndex])[0];
		const updatedObj = { [event.target.value]: currentData[objIndex][oldKey] };
		const newData = [...currentData];
		newData[objIndex] = updatedObj;
		setCurrentData(newData);
		onChange(newData);
	};

	const handleChangeValue = (newValue, objIndex) => {
		const key = Object.keys(currentData[objIndex])[0];
		const newData = [...currentData];
		newData[objIndex] = { ...newData[objIndex], [key]: newValue };
		setCurrentData(newData);
		onChange(newData);
	};

	// Create flat array with additional metadata for rendering
	const flattenedData =
		currentData?.flatMap((obj, objIndex) => {
			return Object.keys(obj).map((key) => ({
				key,
				value: obj[key],
				objIndex,
				uniqueId: `${objIndex}-${key}`, // Create unique identifier for React key
			}));
		}) || [];

	return (
		<div className={classNames("flex h-full flex-col gap-3")}>
			{flattenedData.map((item, idx) => {
				return (
					<div key={item.uniqueId} className="flex w-full gap-2">
						<Input
							type="text"
							value={item.key.trim()}
							className={classNames(duplicateKey ? "input-invalid" : "")}
							placeholder="Type key..."
							onChange={(event) => handleChangeKey(event, item.objIndex)}
							disabled={!isInputField}
							data-testid={testId ? `${testId}-key-${idx}` : undefined}
						/>

						<Input
							type="text"
							value={item.value}
							placeholder="Type a value..."
							onChange={(event) =>
								handleChangeValue(event.target.value, item.objIndex)
							}
							disabled={!isInputField}
							data-testid={testId ? `${testId}-value-${idx}` : undefined}
						/>

						{isList &&
						isInputField &&
						item.objIndex === currentData.length - 1 ? (
							<button
								type="button"
								onClick={() => {
									const newInputList = _.cloneDeep(currentData);
									newInputList.push({ "": "" });
									setCurrentData(newInputList);
									onChange(newInputList);
								}}
								data-testid={testId ? `${testId}-plus-btn-0` : undefined}
							>
								<IconComponent
									name="Plus"
									className={"h-4 w-4 hover:text-accent-foreground"}
								/>
							</button>
						) : isList && isInputField ? (
							<button
								type="button"
								onClick={() => {
									const newInputList = _.cloneDeep(currentData);
									newInputList.splice(item.objIndex, 1);
									setCurrentData(newInputList);
									onChange(newInputList);
								}}
								data-testid={
									testId ? `${testId}-minus-btn-${item.objIndex}` : undefined
								}
							>
								<IconComponent
									name="X"
									className="h-4 w-4 hover:text-status-red"
								/>
							</button>
						) : (
							""
						)}
					</div>
				);
			})}
		</div>
	);
};

export default IOKeyPairInput;
