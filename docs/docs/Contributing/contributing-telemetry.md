---
title: Telemetry
sidebar_position: 0
slug: /contributing-telemetry
---



:::info

This page may contain outdated information. It will be updated as soon as possible.

:::




Our system uses anonymous telemetry to collect essential usage statistics to enhance functionality and user experience. This data helps us identify commonly used features and areas needing improvement, ensuring our development efforts align with what you need.


:::note

We respect your privacy and are committed to protecting your data. We do not collect any personal information or sensitive data. All telemetry data is anonymized and used solely for improving Langflow.

You can opt-out of telemetry by setting the `LANGFLOW_DO_NOT_TRACK` or `DO_NOT_TRACK` environment variable to `true` before running Langflow. This will disable telemetry data collection.

:::




## Data Collected Includes {#1734ed50fb4a4a45aaa84185b44527ca}


### Run {#2d427dca4f0148ae867997f6789e8bfb}

- **IsWebhook**: Indicates whether the operation was triggered via a webhook.
- **Seconds**: Duration in seconds for how long the operation lasted, providing insights into performance.
- **Success**: Boolean value indicating whether the operation was successful, helping identify potential errors or issues.
- **ErrorMessage**: Provides error message details if the operation was unsuccessful, aiding in troubleshooting and enhancements.

### Shutdown {#081e4bd4faec430fb05b657026d1a69c}

- **Time Running**: Total runtime before shutdown, useful for understanding application lifecycle and optimizing uptime.

### Version {#dc09f6aba6c64c7b8dad3d86a7cba6d6}

- **Version**: The specific version of Langflow used, which helps in tracking feature adoption and compatibility.
- **Platform**: Operating system of the host machine, which aids in focusing our support for popular platforms like Windows, macOS, and Linux.
- **Python**: The version of Python used, assisting in maintaining compatibility and support for various Python versions.
- **Arch**: Architecture of the system (e.g., x86, ARM), which helps optimize our software for different hardware.
- **AutoLogin**: Indicates whether the auto-login feature is enabled, reflecting user preference settings.
- **CacheType**: Type of caching mechanism used, which impacts performance and efficiency.
- **BackendOnly**: Boolean indicating whether you are running Langflow in a backend-only mode, useful for understanding deployment configurations.

### Playground {#ae6c3859f612441db3c15a7155e9f920}

- **Seconds**: Duration in seconds for playground execution, offering insights into performance during testing or experimental stages.
- **ComponentCount**: Number of components used in the playground, which helps understand complexity and usage patterns.
- **Success**: Success status of the playground operation, aiding in identifying the stability of experimental features.

### Component {#630728d6654c40a6b8901459a4bc3a4e}

- **Name**: Identifies the component, providing data on which components are most utilized or prone to issues.
- **Seconds**: Time taken by the component to execute, offering performance metrics.
- **Success**: Whether the component operated successfully, which helps in quality control.
- **ErrorMessage**: Details of any errors encountered, crucial for debugging and improvement.

This telemetry data is crucial for enhancing Langflow and ensuring that our development efforts align with your needs. Your feedback and suggestions are invaluable in shaping the future of Langflow, and we appreciate your support in making Langflow better for everyone.

