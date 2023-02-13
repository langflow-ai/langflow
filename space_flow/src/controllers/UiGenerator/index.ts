import axios from "axios";

export function generateUiNode(data: Object) {
    const fields = [];
	Object.keys(data).forEach((field) => {
		if (data[field].required) {
            fields.push(data[field])
		}
	});
    return fields
}
