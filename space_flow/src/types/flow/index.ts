export type flow = {
	name: string;
	id: string;
	data: any;
	chat: Array<{ message: string; isSend: boolean }>;
};
