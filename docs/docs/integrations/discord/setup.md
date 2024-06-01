import Admonition from "@theme/Admonition";

# Setting up a Discord App

This guide will walk you through the process of integrating a Discord bot with Langflow, allowing you to leverage Langflow's features within your Discord server.

## Prerequisites

* A Discord account with access to the server (guild) where you want to integrate the bot.
* Administrator permissions in the target Discord server.

## Step 1: Creating a Discord Application

1. Navigate to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click "New Application."
3. Choose a name for your bot application and agree to Discord's Developer Terms of Service.
4. Click "Create."

## Step 2: Get Application Token

1. Navigate to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Select your application.
3. Click on "Bot" section.
4. In the "Token" section, click on "Reset Token" and confirm the action.  
5. Copy and store the provided token in a safe place.

## Step 3: Configuring Bot User Permissions

1. In the navigation menu, go to the "Bot" section.
2. Under "Privileged Gateway Intents," enable the intents required for your desired Langflow components. Refer to the Langflow component documentation for specific intent requirements.
3. In the "Authorization Methods" section, select "Discord Provided Link."
4. In "Default Install Settings," add the "bot" option and grant the necessary permissions for your bot's functionality.

## Step 4: Adding the Bot to Your Discord Server

1. In the navigation menu, go to the "OAuth2" section, then the "URL Generator" tab.
2. Under "SCOPES," check the "bot" option.
3. Under "BOT PERMISSIONS," select the permissions you configured in Step 2.
4. Copy the generated URL and paste it into your browser.
5. Choose the server where you want to add the bot and click "Continue".
6. Review the requested permissions and click "Authorize".

<Admonition type="info" title="Using Langflow Discord Components">

Langflow offers a variety of Discord components to enhance your bot's capabilities. Here's an overview of the available components (organized logically):

### Message Handling
* **DiscordTextMessageListener:**  Listens for text messages in a channel.
* **DiscordMentionResponse:** Responds to messages where the bot is mentioned.
* **DiscordMessageSender:** Sends messages to a channel or thread.
* **DiscordThreads:** Interacts with threads.

### Media and File Handling
* **DiscordImageSender:** Sends images to a channel.
* **DiscordGetImage:** Retrieves the last n-image messages.
* **DiscordFileSender:** Sends files to a channel.
* **DiscordGetAudioMessage:** Retrieves the last audio message from a channel.
* **DiscordAudioSender:** Sends audio files to a channel.

### Server and Channel Information
* **DiscordGetGuildChannels:** Gets information about channels in a server.
* **DiscordGetGuildUsers:** Gets information about users in a server.
* **DiscordGetChannelMessages:** Retrieves message history from a channel.
* **DiscordBotName:** Retrieves the name of bot account.

### Reactions
* **DiscordAddEmojiReaction:** Adds an emoji reaction to a message.
* **DiscordRemoveEmojiReaction:** Removes an emoji reaction from a message.

Refer to the Langflow documentation for detailed instructions on using each component.

</Admonition>
<Admonition type="info" title="Additional Resources">

- [Discord API Documentation](https://discord.com/developers/docs/quick-start/getting-started)
- [Understanding Discord Resources](https://discord.com/developers/docs/resources/application)

</Admonition>