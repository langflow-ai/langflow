import { GetCodeType } from "@/types/tweaks";

/**
 * Function to generate JavaScript code for interfacing with an API using the LangflowClient class.
 * @param {string} flowId - The id of the flow.
 * @param {boolean} isAuth - Whether the API requires authentication.
 * @param {any[]} tweaksBuildedObject - Customizations applied to the flow.
 * @param {string} [endpointName] - Optional endpoint name.
 * @returns {string} - The JavaScript code as a string.
 */
export default function getJsApiCode({
  flowId,
  isAuth,
  tweaksBuildedObject,
  endpointName,
}: GetCodeType): string {
  let tweaksString = "{}";
  if (tweaksBuildedObject)
    tweaksString = JSON.stringify(tweaksBuildedObject, null, 2);

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
  
            const responseMessage = await response.json();
            if (!response.ok) {
                throw new Error(\`\${response.status} \${response.statusText} - \${JSON.stringify(responseMessage)}\`);
            }
            return responseMessage;
        } catch (error) {
            console.error(\`Error during POST request: \${error.message}\`);
            throw error;
        }
    }
  
    async initiateSession(flowId, inputValue, inputType = 'chat', outputType = 'chat', stream = false, tweaks = {}) {
        const endpoint = \`/api/v1/run/\${flowId}?stream=\${stream}\`;
        return this.post(endpoint, { input_value: inputValue, input_type: inputType, output_type: outputType, tweaks: tweaks });
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
  
    async runFlow(flowIdOrName, inputValue, inputType = 'chat', outputType = 'chat', tweaks, stream = false, onUpdate, onClose, onError) {
        try {
            const initResponse = await this.initiateSession(flowIdOrName, inputValue, inputType, outputType, stream, tweaks);
            if (stream && initResponse?.outputs?.[0]?.outputs?.[0]?.artifacts?.stream_url) {
                const streamUrl = initResponse.outputs[0].outputs[0].artifacts.stream_url;
                console.log(\`Streaming from: \${streamUrl}\`);
                this.handleStream(streamUrl, onUpdate, onClose, onError);
            }
            return initResponse;
        } catch (error) {
          onError('Error initiating session');
        }
    }
  }
  
  async function main(inputValue, inputType = 'chat', outputType = 'chat', stream = false) {
    const flowIdOrName = '${endpointName || flowId}';
    const langflowClient = new LangflowClient('${window.location.protocol}//${window.location.host}',
          ${isAuth ? "'your-api-key'" : "null"});
    const tweaks = ${tweaksString};
  
    try {
        const response = await langflowClient.runFlow(
            flowIdOrName,
            inputValue,
            inputType,
            outputType,
            tweaks,
            stream,
            (data) => console.log("Received:", data.chunk), // onUpdate
            (message) => console.log("Stream Closed:", message), // onClose
            (error) => console.error("Stream Error:", error) // onError
        );
  
        if (!stream && response) {
            const flowOutputs = response.outputs[0];
            const firstComponentOutputs = flowOutputs.outputs[0];
            const output = firstComponentOutputs.outputs.message;
  
            console.log("Final Output:", output.message.text);
        }
    } catch (error) {
        console.error('Main Error:', error.message);
    }
  }
  
  const args = process.argv.slice(2);
  main(
    args[0], // inputValue
    args[1], // inputType
    args[2], // outputType
    args[3] === 'true' // stream
  );
  `;
}
