---
title: Financial report parser
slug: /financial-report-parser
---

import Icon from "@site/src/components/icon";

This flow demonstrates how to parse LLM responses into a structured format.

In this example, the [Chat Input](/components-io#chat-input) component is pre-loaded with a sample financial report to demonstrate extracting `Gross Profit`, `EBITDA`, and `Net Income`.
The [Structured output](/components-processing#structured-output) component is used to extract the financial data from the report, and the [Parser](/components-processing#parser) component is used to convert the extracted data into a structured format.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/)

## Create the financial report parser flow

1. From the Langflow dashboard, click **New Flow**.
2. Select **Financial Report Parser**.

The **Financial Report Parser** flow is created.

![Financial report parser flow](/img/starter-flow-financial-report-parser.png)

## Run the financial report parser flow

1. Add your **OpenAI API key** to the **Language model** model component.
	Optionally, create a [global variable](/configuration-global-variables) for the **OpenAI API key**.

	1. In the **OpenAI API Key** field, click <Icon name="Globe" aria-hidden="True" /> **Globe**, and then click **Add New Variable**.
	2. In the **Variable Name** field, enter `openai_api_key`.
	3. In the **Value** field, paste your OpenAI API Key (`sk-...`).
	4. Click **Save Variable**.
2. To run the flow, click <Icon name="Play" aria-hidden="true"/> **Playground**, and then click **Send**.
The **Chat Input** component is pre-loaded with a sample financial report for demonstration purposes.
The **Playground** returns a structured response:

```text
EBITDA: $900 million , Net Income: $500 million , GROSS_PROFIT: $1.2 billion
```

Inspect the flow to understand how this information was extracted.

3. To inspect the output schema table, in the **Structured Output** component, click **Open table**.
The **Structured Output** component uses the attached **OpenAI** model component as its "brain" to extract financial data into a [DataFrame](/concepts-objects#dataframe-object) with this defined schema.
```text
| Name         | Description           | Type | Multiple |
|--------------|-----------------------|------|----------|
| EBITDA       | description of field  | text | False    |
| NET_INCOME   | description of field  | text | False    |
| GROSS_PROFIT | description of field  | text | False    |
```

4. To inspect the template that contains the extracted data, in the **Parser** component, click <Icon name="Scan" aria-hidden="true"/> **Scan** in the **Template** field.
The **Parser** component converts the extracted data into formatted messages for chat consumption.
Each variable receives its value from the structured outputs.
```text
EBITDA: {EBITDA}  ,  Net Income: {NET_INCOME} , GROSS_PROFIT: {GROSS_PROFIT}
```



