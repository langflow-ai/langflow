export LANGFLOW_DATABASE_URL="mysql+pymysql://${username}:${password}@${host}:3306/${dbname}"
# echo $LANGFLOW_DATABASE_URL
uvicorn --factory src.backend.langflow.main:create_app --host 0.0.0.0 --port 7860 --reload --log-level debug