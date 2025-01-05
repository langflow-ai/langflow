---
title: Auto-saving
slug: /configuration-auto-save
---

Langflow supports both manual and auto-saving functionality.

## Auto-saving {#auto-saving}

When Langflow is in auto-saving mode, all changes are saved automatically. Auto-save progress is indicated in the left side of the top bar.

* When a flow is being saved, a loading icon indicates that the flow is being saved in the database.

* If you try to exit the flow page before auto-save completes, you are prompted to confirm you want to exit before the flow has saved.

* When the flow has successfully saved, click **Exit**.

## Disable auto-saving {#environment}

To disable auto-saving, 

1. Set an environment variable in your `.env` file.

```env
LANGFLOW_AUTO_SAVING=false
```

2. Start Langflow with the values from your `.env` file.

```shell
python -m langflow run --env-file .env
```

Alternatively, disable auto-saving by passing the `--no-auto-saving` flag at startup.

```shell
python -m langflow --no-auto-saving
```

## Save a flow manually {#manual-saving}

When auto-saving is disabled, you will need to manually save your flow when making changes.

To manually save your flow, click the **Save** button or enter Ctrl+S or Command+S.

If you try to exit after making changes and not saving, a confirmation dialog appears.

