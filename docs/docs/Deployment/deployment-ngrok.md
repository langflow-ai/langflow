---
title: Ngrok
sidebar_position: 6
slug: /deployment-ngrok
---

## Deploy on Ngrok {#20a959b7047e44e490cc129fd21895c0}

---

[Ngrok](https://ngrok.com/) is a tool that creates a secure tunnel to your local machine. It provides a public URL that you can use to access your Langflow instance from anywhere, making it perfect for development, testing, and sharing your Langflow instance without deploying to a cloud service.

Deploying Langflow with Ngrok involves the following steps:

1. **Create Ngrok Account**:

   - Visit [ngrok.com](https://ngrok.com/) and create an account
   - After signing up, go to the [Auth Token](https://dashboard.ngrok.com/get-started/your-authtoken) section
   - Copy your authentication token for later use

2. **Set Up Environment**:

   - Clone the Langflow repository:
     ```bash
     git clone https://github.com/langflow-ai/langflow.git
     ```
   - Navigate to the project directory:
     ```bash
     cd langflow
     ```
   - Create a `.env` file in the root directory and add your Ngrok authentication token:
     ```bash
     NGROK_AUTH_TOKEN=your_auth_token_here
     ```

3. **Start Langflow**:

   - In the project directory, start Langflow using the CLI:
     ```bash
     make run_cli
     ```
   - Wait for the application to start
   - Verify it's running by visiting `http://0.0.0.0:7860/flows` in your browser

4. **Enable Ngrok Tunnel**:
   - Once Langflow is running, select the deployment with Ngrok option
   - Ngrok will create a public URL for your local instance
   - Copy the provided URL - it will look something like `https://xxxx-xx-xx-xxx-xx.ngrok.io`

Your local Langflow instance is now accessible online through the Ngrok URL. Anyone with the URL can access your instance, making it easy to share and test your flows.

### Important Notes

- The free Ngrok plan has some limitations:
  - Sessions expire after a few hours
  - URLs change each time you restart the tunnel
  - Limited number of concurrent connections
- For production use, consider upgrading to a paid Ngrok plan or using a cloud deployment solution
- Keep your authentication token secure and never commit it to version control
- The Ngrok URL provides access to your local machine, so be careful about what you expose

### Troubleshooting

If you encounter issues:

- Verify your authentication token is correct
- Ensure Langflow is running locally before starting Ngrok
- Check that port 7860 is not being used by another application
- Make sure your firewall isn't blocking the connection

By following these steps, you'll have a publicly accessible Langflow instance running through Ngrok, perfect for development and testing purposes.
