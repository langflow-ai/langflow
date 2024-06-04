# Package the flow as docker image

You can package the flow as a docker image and refer to it in the chart.

```
docker build -t langflow-just-chat .
```

Then refer to this image in the `values.yaml`:

```yaml
image:
  repository: langflow-just-chat
  tag: latest
```
