# :whale: Docker compose
This will run the backend and frontend in separate containers. The frontend will be available at `localhost:3000` and the backend at `localhost:7860`.
```bash
docker compose up --build
# or
make dev build=1
```