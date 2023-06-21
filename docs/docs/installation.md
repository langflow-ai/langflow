# 📦 How to install?

## Installation

You can install LangFlow from pip:

```bash
pip install langflow
```

Next, run:

```bash
langflow
```

---

## Run Locally

LangFlow can run locally by cloning the repository and installing the dependencies. We recommend using a virtual environment to isolate the dependencies from your system.

Before you start, make sure you have the following installed:

- Poetry
- Node.js

Then install the dependencies and start the development server for the backend:

```bash
poetry install
make run_backend
```

And the frontend:

```bash
cd src/frontend
npm install
npm start
```

---

## Docker compose

The following snippet will run the backend and frontend in separate containers. The frontend will be available at `localhost:3000` and the backend at `localhost:7860`.

```bash
docker compose up --build
# or
make dev build=1
```