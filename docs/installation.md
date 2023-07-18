# How to install?
## Installation

You can install LangFlow from pip:

```py
pip install langflow
```

Next, run:

```py
python -m langflow
```

or

```py
langflow
```

---

## Run Locally

Run locally by cloning the repository and installing the dependencies. We recommend using a virtual environment to isolate the dependencies from your system.

<br>

Before you start, make sure you have the following installed:

- Poetry
- Node.js

For the backend, you will need to install the dependencies and start the development server.

```bash
poetry install
make run_backend
```

For the frontend, you will need to install the dependencies and start the development server.

```bash
cd src/frontend
npm install
npm start
```

---

## Docker compose

This will run the backend and frontend in separate containers. The frontend will be available at `localhost:3000` and the backend at `localhost:7860`.

```bash
docker compose up --build
# or
make dev build=1
```
