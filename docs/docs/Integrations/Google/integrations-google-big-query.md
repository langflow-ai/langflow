---
title: Integrate Google BigQuery with Langflow
slug: /integrations-google-big-query
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Langflow integrates with [Google BigQuery](https://cloud.google.com/bigquery) through the BigQuery component, allowing you to execute SQL queries and retrieve data from your BigQuery datasets.

## Prerequisites

* A [Google Cloud project](https://developers.google.com/workspace/guides/create-project) with the BigQuery API enabled
* A [service account](https://developers.google.com/workspace/guides/create-credentials#service-account) with the **BigQuery Job User** role
* A [BigQuery dataset and table](https://cloud.google.com/bigquery/docs/datasets-intro)

## Create a service account with BigQuery access

1. Select and enable your Google Cloud project.
For more information, see [Create a Google Cloud project](https://developers.google.com/workspace/guides/create-project).
2. Create a service account in your Google Cloud project.
For more information, see [Create a service account](https://developers.google.com/workspace/guides/create-credentials#service-account).
3. Assign the **BigQuery Job User** role to your new account.
This role allows Langflow to access BigQuery resources with the service account.
You may also need to allow access to your BigQuery dataset.
For more information, see [BigQuery access control with IAM](https://cloud.google.com/bigquery/docs/access-control).
4. To generate a new JSON key for the service account, navigate to your service account.
5. Click **Add Key**, and then click **Create new key**.
6. Under **Key type**, select **JSON**, and then click **Create**.
A JSON private key file is downloaded to your machine.
Now that you have a service account and a JSON private key, you need to configure the credentials in the Langflow BigQuery component.

## Configure credentials in the Langflow component

With your service account configured and your credentials JSON file created, follow these steps to authenticate the Langflow application.

1. Create a new project in Langflow.
2. From the components sidebar, drag and drop the BigQuery component to your workspace.
3. In the BigQuery component's **Upload Service Account JSON** field, click **Select file**.
4. In the **My Files** pane, select **Click or drag files here**.
Your file browser opens.
5. In your file browser, select the service account JSON file, and then click **Open**.
6. In the **My Files** pane, select your service account JSON file, and then click **Select files**.
The BigQuery component can now query your datasets and tables using your service account JSON file.

## Query a BigQuery dataset

With your component credentials configured, query your BigQuery datasets and tables to confirm connectivity.

1. Connect a **Chat input** and **Chat output** component to the BigQuery component.
The flow looks like this:
![BigQuery component connected to chat input and output](/img/google/integrations-bigquery.png)
2. Open the **Playground**, and then submit a valid SQL query.
This example queries a table of Oscar winners stored within a BigQuery dataset called `the_oscar_award`.
    <Tabs>
      <TabItem value="sql query" label="SQL query" default>

    ```sql
    SELECT film, category, year_film
    FROM `big-query-langflow-project.the_oscar_award.oscar_winners`
    WHERE winner = TRUE
    LIMIT 10
    ```

      </TabItem>
      <TabItem value="result" label="Result">

    ```text
    film	category	year_film
    The Last Command	ACTOR	1927
    7th Heaven	ACTRESS	1927
    The Dove;	ART DIRECTION	1927
    Sunrise	CINEMATOGRAPHY	1927
    Sunrise	CINEMATOGRAPHY	1927
    Two Arabian Knights	DIRECTING (Comedy Picture)	1927
    7th Heaven	DIRECTING (Dramatic Picture)	1927
    Wings	ENGINEERING EFFECTS	1927
    Wings	OUTSTANDING PICTURE	1927
    Sunrise	UNIQUE AND ARTISTIC PICTURE	1927
    ```
      </TabItem>
    </Tabs>

    A successful chat confirms the component can access the BigQuery table.

