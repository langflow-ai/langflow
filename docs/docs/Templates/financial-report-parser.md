---
title: Financial report parser
slug: /financial-report-parser
---

import Icon from "@site/src/components/icon";

Build a **Financial Report Parser** flow with the [Structured output](/docs/components-helpers#structured-output) and [Parser](/docs/components-processing#parser) components to parse LLM responses into a structured format.

In this example, the **Chat Input** component is pre-loaded with a sample financial report to demonstrate extracting `Gross Profit`, `EBITDA`, and `Net Income`.

## Prerequisites

- [A running Langflow instance](/docs/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/)

## Create the financial report parser flow

1. From the Langflow dashboard, click **New Flow**.
2. Select **Financial Report Parser**.

The **Financial Report Parser** flow is created.

![](/img/starter-flow-financial-report-parser.png)

## Run the memory chatbot flow

1. Add your OpenAI API key to the OpenAI model.
2. Click the **Playground** button, and then click **Send**.
The **Chat Input** component is pre-loaded with a sample financial report for demonstration purposes.
The chat returns a structured response:

```text
EBITDA: $900 million , Net Income: $500 million , GROSS_PROFIT: $1.2 billion
```

Inspect the flow to understand how this information was extracted.

3. To inspect the output schema table, in the **Structured Output** component, click **Open table**.
The **Structured Output** component uses the attached **OpenAI** model component as its "brain" to extract financial data into a [DataFrame](/docs/concepts-objects#dataframe-object) with this defined schema.
```text
| Name         | Description           | Type | Multiple |
|--------------|-----------------------|------|----------|
| EBITDA       | description of field  | text | False    |
| NET_INCOME   | description of field  | text | False    |
| GROSS_PROFIT | description of field  | text | False    |
```

4. To inspect the template that contains the extracted data, in the **Parser** component, click the <Icon name="Scan" aria-hidden="true"/> **Scan** icon in the **Template** field.
The **Parser** component converts the extracted data into formatted messages for chat consumption.
Each variable receives its value from the structured outputs.
```text
EBITDA: {EBITDA}  ,  Net Income: {NET_INCOME} , GROSS_PROFIT: {GROSS_PROFIT}
```



