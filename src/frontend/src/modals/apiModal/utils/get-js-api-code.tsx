/**
 * Function to generate JavaScript code for interfacing with an API using the LangflowClient class.
 * @param {string} flowId - The id of the flow.
 * @param {boolean} isAuth - Whether the API requires authentication.
 * @param {any[]} tweaksBuildedObject - Customizations applied to the flow.
 * @param {string} [endpointName] - Optional endpoint name.
 * @returns {string} - The JavaScript code as a string.
 */
export default function getJsApiCode(
  flowId: string,
  isAuth: boolean,
  tweaksBuildedObject: any[],
  endpointName?: string | null,
): string {
  let tweaksString = "{}";
  if (tweaksBuildedObject && tweaksBuildedObject.length > 0) {
    const tweaksObject = tweaksBuildedObject[0];
    if (!tweaksObject) {
      throw new Error("Expected tweaks object is not provided.");
    }
    tweaksString = JSON.stringify(tweaksObject, null, 2);
  }
  return `class LangflowClient {
    constructor(baseURL, apiKey) {
        this.baseURL = baseURL;
        this.apiKey = apiKey;
    }
    async post(endpoint, body, headers = {"Content-Type": "application/json"}) {
        if (this.apiKey) {
            headers["Authorization"] = \`Bearer \${this.apiKey}\`;
        }
        const url = \`\${this.baseURL}\${endpoint}\`;
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(body)
            });
            if (!response.ok) {
                throw new Error(\`HTTP error! Status: \${response.status}\`);
            }
            return await response.json();
        } catch (error) {
            console.error('Request Error:', error);
            throw error;
        }
    }

    async initiateSession(flowId, inputValue, stream = false, tweaks = {}) {
        const endpoint = \`/api/v1/run/\${flowId}?stream=\${stream}\`;
        return this.post(endpoint, { input_value: inputValue, tweaks: tweaks });
    }

    handleStream(streamUrl, onUpdate, onClose, onError) {
        const eventSource = new EventSource(streamUrl);

        eventSource.onmessage = event => {
            const data = JSON.parse(event.data);
            onUpdate(data);
        };

        eventSource.onerror = event => {
            console.error('Stream Error:', event);
            onError(event);
            eventSource.close();
        };

        eventSource.addEventListener("close", () => {
            onClose('Stream closed');
            eventSource.close();
        });

        return eventSource;
    }

    async runFlow(flowIdOrName, inputValue, tweaks, stream = false, onUpdate, onClose, onError) {
        try {
            const initResponse = await this.initiateSession(flowIdOrName, inputValue, stream, tweaks);
            console.log('Init Response:', initResponse);
            if (stream && initResponse && initResponse.outputs && initResponse.outputs[0].outputs[0].artifacts.stream_url) {
                const streamUrl = initResponse.outputs[0].outputs[0].artifacts.stream_url;
                console.log(\`Streaming from: \${streamUrl}\`);
                this.handleStream(streamUrl, onUpdate, onClose, onError);
            }
            return initResponse;
        } catch (error) {
            console.error('Error running flow:', error);
            onError('Error initiating session');
        }
    }
}

async function main() {
    const flowIdOrName = '${endpointName || flowId}';
    const inputValue = 'User message';
    const stream = false;
    const langflowClient = new LangflowClient('${window.location.protocol}//${window.location.host}',
        ${isAuth ? "'your-api-key'" : "null"});
    const tweaks = ${tweaksString};
    response = await langflowClient.runFlow(
        flowIdOrName,
        inputValue,
        tweaks,
        stream,
        (data) => console.log("Received:", data.chunk), // onUpdate
        (message) => console.log("Stream Closed:", message), // onClose
        (error) => console.log("Stream Error:", error) // onError
    );
    if (!stream) {
        const flowOutputs = response.outputs[0];
        const firstComponentOutputs = flowOutputs.outputs[0];
        const output = firstComponentOutputs.outputs.message;

        console.log("Final Output:", output.message.text);
    }
}

main();`;
}
