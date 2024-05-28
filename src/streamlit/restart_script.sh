kill $(ps aux | grep '[s]treamlit run ' | awk '{print $2}')
streamlit run script.py --browser.serverPort 5001 --server.port 5001
