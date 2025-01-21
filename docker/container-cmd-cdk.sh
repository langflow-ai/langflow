export LANGFLOW_DATABASE_URL="mysql+pymysql://${username}:${password}@${host}:3306/${dbname}"
echo $LANGFLOW_DATABASE_URL
make backend