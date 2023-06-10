import { Dialog, Transition } from '@headlessui/react';
import {
	XMarkIcon,
	ArrowDownTrayIcon,
	DocumentDuplicateIcon,
	ComputerDesktopIcon,
	ArrowUpTrayIcon,
	ArrowLeftIcon,
} from '@heroicons/react/24/outline';
import { Fragment, useContext, useRef, useState } from 'react';
import { PopUpContext } from '../../contexts/popUpContext';
import { TabsContext } from '../../contexts/tabsContext';
import ButtonBox from '../importModal/buttonBox';
import { getExamples } from '../../controllers/API';
import { error } from 'console';
import { alertContext } from '../../contexts/alertContext';
import LoadingComponent from '../../components/loadingComponent';
import { FlowType } from '../../types/flow';
import { classNames, snakeToSpaces, toNormalCase } from '../../utils';
import './index.css';
import axios, { AxiosResponse } from 'axios';

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
								<GraphApp />
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

const options = {
	layout: {
		hierarchical: false,
	},
	edges: {
		color: '#34495e',
	},
};

function GraphApp() {
	const [graphState, setGraphState] = useState({
		nodes: [],
		edges: [],
	});

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
	};

	const queryStatelessPrompt = (prompt, apiKey) => {
		fetch('prompts/stateless.prompt')
			.then((response) => response.text())
			.then((text) => text.replace('$prompt', prompt))
			.then((prompt) => {
				console.log(prompt);

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
						console.log(response);
						const text = choices[0].text;
						console.log(text);
						const updates = JSON.parse(text);
						console.log('openai output');
						console.log(updates);

						updateGraph(updates);

						document.getElementsByClassName('searchBar')[0].value =
							'';
						document.body.style.cursor = 'default';
						document.getElementsByClassName(
							'generateButton'
						)[0].disabled = false;
					})
					.catch((error) => {
						console.log(error);
						alert(error);
					});
			});
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

	const createGraph = () => {
		document.body.style.cursor = 'wait';

		document.getElementsByClassName('generateButton')[0].disabled = true;
		const prompt = document.getElementsByClassName('searchBar')[0].value;
		const apiKey =
			document.getElementsByClassName('apiKeyTextField')[0].value;

		queryPrompt(prompt, apiKey);
	};

	console.log('graphState', graphState);

	return (
		<div className='container'>
			<h1 className='headerText'>GraphGPT 🔎</h1>
			<p className='subheaderText'>
				Build complex, directed graphs to add structure to your ideas
				using natural language. Understand the relationships between
				people, systems, and maybe solve a mystery.
			</p>
			<p className='opensourceText'>
				<a href='https://github.com/varunshenoy/graphgpt'>
					GraphGPT is open-source
				</a>
				&nbsp;🎉
			</p>
			<center>
				<div className='inputContainer'>
					<input
						className='searchBar'
						placeholder='Describe your graph...'
					></input>
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
			<div className='graphContainer'>
				{/* <Graph graph={graphState} options={options} style={{ height: "640px" }} /> */}
			</div>
			<p className='footer'>
				Pro tip: don't take a screenshot! You can right-click and save
				the graph as a .png 📸
			</p>
		</div>
	);
}
