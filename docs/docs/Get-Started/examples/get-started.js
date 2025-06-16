const readline = require('readline');

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

const url = 'http://localhost:7860/api/v1/run/29deb764-af3f-4d7d-94a0-47491ed241d6';

// Store the previous answer
let previousAnswer = null;

async function askAgent(question) {
    const payload = {
        "output_type": "chat",
        "input_type": "chat",
        "input_value": question
    };

    const options = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    };

    try {
        const response = await fetch(url, options);
        const data = await response.json();
        
        // Extract the message from the nested response
        const message = data.outputs[0].outputs[0].outputs.message.message;
        return message;
    } catch (error) {
        return `Error: ${error.message}`;
    }
}

async function startChat() {
    console.log("\nAsk the agent anything, such as 'What is 15 * 7?' or 'What is the capital of France?'");
    console.log("Type 'quit' to exit or 'compare' to see the previous answer");

    const askQuestion = () => {
        rl.question('\nYour question: ', async (userQuestion) => {
            if (userQuestion.toLowerCase() === 'quit') {
                rl.close();
                return;
            }

            if (userQuestion.toLowerCase() === 'compare') {
                if (previousAnswer) {
                    console.log(`\nPrevious answer was: ${previousAnswer}`);
                } else {
                    console.log("\nNo previous answer to compare with!");
                }
                askQuestion();
                return;
            }

            const result = await askAgent(userQuestion);
            console.log(`\nAgent's answer: ${result}`);
            previousAnswer = result;
            askQuestion();
        });
    };

    askQuestion();
}

startChat(); 