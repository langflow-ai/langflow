import { Dialog, Transition } from '@headlessui/react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { Fragment, useContext, useEffect, useRef, useState } from 'react';
import { PopUpContext } from '../../contexts/popUpContext';
import { TabsContext } from '../../contexts/tabsContext';
import { getExamples } from '../../controllers/API';
import { alertContext } from '../../contexts/alertContext';
import { FlowType } from '../../types/flow';
import './index.css';
import templates from './templates';
import { v4 as uuidv4 } from 'uuid';
import messageSummary from './message_summary.json';

export default function PromptImportModal() {
	const [open, setOpen] = useState(true);
	const { setErrorData } = useContext(alertContext);
	const { closePopUp } = useContext(PopUpContext);
	const ref = useRef();
	const [showExamples, setShowExamples] = useState(false);
	const [loadingExamples, setLoadingExamples] = useState(false);
	const [examples, setExamples] = useState<FlowType[]>([]);
	const { uploadFlow, addFlow } = useContext(TabsContext);
	function setModalOpen(x: boolean) {
		setOpen(x);
		if (x === false) {
			setTimeout(() => {
				closePopUp();
			}, 300);
		}
	}

	function handleExamples() {
		setLoadingExamples(true);
		getExamples()
			.then((result) => {
				setLoadingExamples(false);
				setExamples(result);
			})
			.catch((error) =>
				setErrorData({
					title: 'there was an error loading examples, please try again',
					list: [error.message],
				})
			);
	}

	return (
		<Transition.Root show={open} appear={true} as={Fragment}>
			<Dialog
				as='div'
				className='relative z-10'
				onClose={setModalOpen}
				initialFocus={ref}
			>
				<Transition.Child
					as={Fragment}
					enter='ease-out duration-300'
					enterFrom='opacity-0'
					enterTo='opacity-100'
					leave='ease-in duration-200'
					leaveFrom='opacity-100'
					leaveTo='opacity-0'
				>
					<div className='fixed inset-0 bg-gray-500 dark:bg-gray-600 dark:bg-opacity-75 bg-opacity-75 transition-opacity' />
				</Transition.Child>

				<div className='fixed inset-0 z-10 overflow-y-auto'>
					<div className='flex h-full items-end justify-center p-4 text-center sm:items-center sm:p-0'>
						<Transition.Child
							as={Fragment}
							enter='ease-out duration-300'
							enterFrom='opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95'
							enterTo='opacity-100 translate-y-0 sm:scale-100'
							leave='ease-in duration-200'
							leaveFrom='opacity-100 translate-y-0 sm:scale-100'
							leaveTo='opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95'
						>
							<Dialog.Panel className='relative flex flex-col justify-between transform h-[600px] overflow-hidden rounded-lg bg-white dark:bg-gray-800 text-left shadow-xl transition-all sm:my-8 w-[776px]'>
								<div className=' z-50 absolute top-0 right-0 hidden pt-4 pr-4 sm:block'>
									<button
										type='button'
										className='rounded-md text-gray-400 hover:text-gray-500'
										onClick={() => {
											setModalOpen(false);
										}}
									>
										<span className='sr-only'>Close</span>
										<XMarkIcon
											className='h-6 w-6'
											aria-hidden='true'
										/>
									</button>
								</div>
								<GraphApp
									addFlow={addFlow}
									setModalOpen={setModalOpen}
								/>
							</Dialog.Panel>
						</Transition.Child>
					</div>
				</div>
			</Dialog>
		</Transition.Root>
	);
}

const DEFAULT_PARAMS = {
	model: 'text-davinci-003',
	temperature: 0.3,
	max_tokens: 800,
	top_p: 1,
	frequency_penalty: 0,
	presence_penalty: 0,
};

const SELECTED_PROMPT = 'STATELESS';

function GraphApp({ addFlow, setModalOpen }) {
	const [graphState, setGraphState] = useState({
		nodes: [],
		edges: [],
	});

	useEffect(() => {
		return () => {
			clearState();
		};
	}, []);

	const clearState = () => {
		setGraphState({
			nodes: [],
			edges: [],
		});
	};

	const updateGraph = (updates) => {
		// updates will be provided as a list of lists
		// each list will be of the form [ENTITY1, RELATION, ENTITY2] or [ENTITY1, COLOR]

		let current_graph = JSON.parse(JSON.stringify(graphState));

		if (updates.length === 0) {
			return;
		}

		// check type of first element in updates
		if (typeof updates[0] === 'string') {
			// updates is a list of strings
			updates = [updates];
		}

		updates.forEach((update) => {
			if (update.length === 3) {
				// update the current graph with a new relation
				const [entity1, relation, entity2] = update;

				// check if the nodes already exist
				let node1 = current_graph.nodes.find(
					(node) => node.id === entity1
				);
				let node2 = current_graph.nodes.find(
					(node) => node.id === entity2
				);

				if (node1 === undefined) {
					current_graph.nodes.push({
						id: entity1,
						label: entity1,
						color: '#ffffff',
					});
				}

				if (node2 === undefined) {
					current_graph.nodes.push({
						id: entity2,
						label: entity2,
						color: '#ffffff',
					});
				}

				// check if an edge between the two nodes already exists and if so, update the label
				let edge = current_graph.edges.find(
					(edge) => edge.from === entity1 && edge.to === entity2
				);
				if (edge !== undefined) {
					edge.label = relation;
					return;
				}

				current_graph.edges.push({
					from: entity1,
					to: entity2,
					label: relation,
				});
			} else if (update.length === 2 && update[1].startsWith('#')) {
				// update the current graph with a new color
				const [entity, color] = update;

				// check if the node already exists
				let node = current_graph.nodes.find(
					(node) => node.id === entity
				);

				if (node === undefined) {
					current_graph.nodes.push({
						id: entity,
						label: entity,
						color: color,
					});
					return;
				}

				// update the color of the node
				node.color = color;
			} else if (update.length === 2 && update[0] == 'DELETE') {
				// delete the node at the given index
				const [_, index] = update;

				// check if the node already exists
				let node = current_graph.nodes.find(
					(node) => node.id === index
				);

				if (node === undefined) {
					return;
				}

				// delete the node
				current_graph.nodes = current_graph.nodes.filter(
					(node) => node.id !== index
				);

				// delete all edges that contain the node
				current_graph.edges = current_graph.edges.filter(
					(edge) => edge.from !== index && edge.to !== index
				);
			}
		});
		setGraphState(current_graph);
		parseGraphData(current_graph);
	};

	const nodes = [
		'AzureChatOpenAI',
		'LLMChain',
		'PromptTemplate',
		'飞书群聊回复',
		'飞书群聊读取',
		'飞书妙计读取',
		'飞书任务生成',
		'飞书文档生成',
	];

	const queryStatelessPrompt = async (promptText, apiKey) => {
		const prompt = `Given a prompt, extrapolate as many relationships as possible from it and provide a list of updates.\n\nIf an update is a relationship, provide [ENTITY 1, RELATIONSHIP, ENTITY 2]. The relationship is directed, so the order matters. Match the ENTITY 1 and ENTITY 2 as closely as possible from one of [${nodes}]. Replace the original ENTITY with the matched one.\n\nExample:\nprompt: 构建一个工作流，从“飞书群消息读取组件”、“Prompt组件”、“OpenAI组件”输出到同一个“LLM组件”，再从这个“LLM组件”输出到“飞书群消息回复组件”\nupdates:\n[["飞书群聊读取", "输出", "LLMChain"], ["PromptTemplate", "输出", "LLMChain"], ["AzureChatOpenAI", "输出", "LLMChain"], ["LLMChain", "输出", "飞书群聊回复"]]\n\nprompt: ${promptText}\nupdates:\n`;

		const params = {
			...DEFAULT_PARAMS,
			prompt: prompt,
			stop: '\n',
		};

		const requestOptions = {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				Authorization: 'Bearer ' + String(apiKey),
			},
			body: JSON.stringify(params),
		};
		fetch('https://api.openai.com/v1/completions', requestOptions)
			.then((response) => {
				if (!response.ok) {
					switch (response.status) {
						case 401: // 401: Unauthorized: API key is wrong
							throw new Error(
								'Please double-check your API key.'
							);
						case 429: // 429: Too Many Requests: Need to pay
							throw new Error(
								'You exceeded your current quota, please check your plan and billing details.'
							);
						default:
							throw new Error(
								'Something went wrong with the request, please check the Network log'
							);
					}
				}
				return response.json();
			})
			.then((response) => {
				const { choices } = response;
				const text = choices[0].text;
				console.log(text);

				const updates = JSON.parse(text);
				console.log('openai output');

				updateGraph(updates);

				document.getElementsByClassName('searchBar')[0].value = '';
				document.body.style.cursor = 'default';
				document.getElementsByClassName('generateButton')[0].disabled =
					false;
			})
			.catch((error) => {
				console.log(error);
				alert(error);
				document.getElementsByClassName('generateButton')[0].disabled =
					false;
			});
	};

	const parseGraphData = (data) => {
		const replacedNodes = data.nodes.map((node) => {
			const id = uuidv4();
			const template = templates[node?.id];
			if (template?.id) {
				template.id = id;
			}
			if (template?.data?.id) {
				template.data.id = id;
			}
			return template;
		});

		const replaceEdges = data.edges.map((edge) => {
			const { from, to } = edge;
			const sourceNode = replacedNodes.find(
				(node) => node?.data?.type === from
			);
			const targetNode = replacedNodes.find(
				(node) => node?.data?.type === to
			);
			return {
				source: sourceNode?.id,
				sourceHandle: [
					sourceNode?.data.type,
					sourceNode?.id,
					...sourceNode?.data?.node.base_classes,
				].join('|'),
				target: targetNode?.id,
				targetHandle: [
					...sourceNode?.data.node?.targetHandleBase,
					targetNode?.id,
				].join('|'),
				style: { stroke: 'inherit' },
			};
		});

		setModalOpen(false);
		const json = {
			data: {
				nodes: replacedNodes,
				edges: replaceEdges,
				viewport: {
					x: -1000,
					y: -500,
					zoom: 1,
				},
			},
		};
		console.log(
			'Dogtiti ~ file: index.tsx:372 ~ parseGraphData ~ json:',
			json
		);
		addFlow(json);
	};

	const queryPrompt = (prompt, apiKey) => {
		if (SELECTED_PROMPT === 'STATELESS') {
			queryStatelessPrompt(prompt, apiKey);
		} else {
			alert('Please select a prompt');
			document.body.style.cursor = 'default';
			document.getElementsByClassName('generateButton')[0].disabled =
				false;
		}
	};

	const promptStr =
		'构建一个工作流，从“AzureChatOpenAI”、“PromptTemplate”输出到同一个“LLMChain”';

	const apikey = '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';

	const createGraph = () => {
		document.body.style.cursor = 'wait';

		document.getElementsByClassName('generateButton')[0].disabled = true;
		const prompt = document.getElementsByClassName('searchBar')[0].value;
		const apiKey =
			document.getElementsByClassName('apiKeyTextField')[0].value;

		queryPrompt(prompt, apiKey);
	};

	return (
		<div className='container'>
			<h1 className='headerText'>GraphGPT 🔎</h1>
			<p className='subheaderText'>
				Build complex, directed graphs to add structure to your ideas
				using natural language. Understand the relationships between
				people, systems, and maybe solve a mystery.
			</p>
			<center>
				<div className='inputContainer'>
					<textarea
						rows={5}
						className='searchBar'
						placeholder='Describe your graph...'
					></textarea>
					<input
						className='apiKeyTextField'
						type='password'
						placeholder='Enter your OpenAI API key...'
					></input>
					<button className='generateButton' onClick={createGraph}>
						Generate
					</button>
					<button className='clearButton' onClick={clearState}>
						Clear
					</button>
				</div>
			</center>
		</div>
	);
}
