---
title: Auto-saving
sidebar_position: 6
slug: /configuration-auto-save
---

Langflow currently supports manual saving and auto-saving functionality. This section will introduce both of them and instruct you on how to disable or enable auto-save.

## Auto-saving {#auto-saving}

When Langflow is in Auto-saving mode, all changes you make are going to be saved automatically. You can see the saving progress at the left side of the top bar. When the flow is being saved, a Loading indicator will appear, indicating that the flow is being saved in the database.

## Disable Auto Saving {#environment}

In Langflow, all changes made in the flows are saved automatically. However, you may prefer to disable this functionality, if you want a quick way to prototype and test changes before they are actually saved to the database.

If you wish to disable this functionality, you can run Langflow with an environment variable to tell Langflow to use manual saving.

```shell
langflow --auto-saving=false

```

If you installed the local version of Langflow, you can set an environment variable and load it automatically by inserting this line into the ".env" file inside the directory.

```env
LANGFLOW_AUTO_SAVING=false
```

I
