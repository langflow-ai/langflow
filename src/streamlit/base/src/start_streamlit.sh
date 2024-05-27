#!/bin/bash

# Define o caminho do arquivo ou diretório para monitorar
DIRECTORY_TO_WATCH="."

# O comando para iniciar o Streamlit
STREAMLIT_COMMAND="streamlit run app.py"

# Utiliza watchexec para monitorar mudanças nos arquivos Python no diretório especificado
# e reiniciar o Streamlit automaticamente
watchexec --exts py --watch $DIRECTORY_TO_WATCH -- $STREAMLIT_COMMAND