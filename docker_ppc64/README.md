------- build LANGFLOW 1.9.2 ppc64

python 3.12

podman build --cgroup-manager cgroupfs -f Dockerfile.backend --rm=true -t local/langflow_backend_ppc64le:1.9.2a .

podman build --cgroup-manager cgroupfs -f Dockerfile.frontend --rm=true -t local/langflow_frontend_ppc64le:1.9.2a .



podman pull ppc64le/postgres:17



Deployment using podman-compose



networks:
  lfnet01:
    driver: bridge

volumes:
  pgdata:
    driver: local
  components:
    driver: local
    driver_opts:
      o: bind
      type: none
      device: /app/components

services:
  lf_postgres01:
    container_name: lf_postgres01    
    image: ppc64le/postgres:17 
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=mysecretpassword
      - POSTGRES_DB=langflow
      - PGDATA=/var/lib/postgresql/data/pgdata
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks: [lfnet01]

  lf_backend:
    container_name: lf_backend
    image: local/langflow_backend_ppc64le:1.9.2a 
    environment:
      - LANGFLOW_DATABASE_URL=postgresql+psycopg://postgres:mysecretpassword@lf_postgres01:5432/langflow
      - LANGFLOW_COMPONENTS_PATH=/app/custom_components
    volumes:
      - components:/app/custom_components:z
    ports:
      - 7860:7860
    networks: [lfnet01]
    depends_on:
      - lf_postgres01

  lf_frontend:
    container_name: lf_frontend
    image: local/langflow_frontend_ppc64le:1.9.2a
    environment:
      - BACKEND_URL="http://lf_backend:7860"
      - FRONTEND_PORT=8080
    ports:
      - 8080:8080
    depends_on:
      - lf_backend



===========================


Access to http://host:8080 
