# [![Langflow](./docs/static/img/hero.png)](https://www.langflow.org)

<p align="center"><strong>
    Un Framework visual para crear aplicaciones de agentes autónomos y RAG
</strong></p>
<p align="center" style="font-size: 12px;">
    De código abierto, construido en Python, totalmente personalizable, agnóstico en cuanto a modelos y bases de datos
</p>

<p align="center" style="font-size: 12px;">
    <a href="https://docs.langflow.org" style="text-decoration: underline;">Documentación</a> -
    <a href="https://discord.com/invite/EqksyE2EX9" style="text-decoration: underline;">Únete a nuestro Discord</a> -
    <a href="https://twitter.com/langflow_ai" style="text-decoration: underline;">Síguenos en X</a> -
    <a href="https://huggingface.co/spaces/Langflow/Langflow" style="text-decoration: underline;">Demostración</a>
</p>

<p align="center">
    <a href="https://github.com/langflow-ai/langflow">
        <img src="https://img.shields.io/github/stars/langflow-ai/langflow">
    </a>
    <a href="https://discord.com/invite/EqksyE2EX9">
        <img src="https://img.shields.io/discord/1116803230643527710?label=Discord">
    </a>
</p>

<div align="center">
  <a href="./README.md"><img alt="README en Inglés" src="https://img.shields.io/badge/English-d9d9d9"></a>
  <a href="./README.PT.md"><img alt="README en Portugués" src="https://img.shields.io/badge/Português-d9d9d9"></a>
  <a href="./README.ES.md"><img alt="README en Español" src="https://img.shields.io/badge/Español-d9d9d9"></a>
  <a href="./README.zh_CN.md"><img alt="README en Chino Simplificado" src="https://img.shields.io/badge/简体中文-d9d9d9"></a>
  <a href="./README.ja.md"><img alt="README en Japonés" src="https://img.shields.io/badge/日本語-d9d9d9"></a>
  <a href="./README.KR.md"><img alt="README en Coreano" src="https://img.shields.io/badge/한국어-d9d9d9"></a>
</div>

<p align="center">
  <img src="./docs/static/img/langflow_basic_howto.gif" alt="Tu GIF" style="border: 3px solid #211C43;">
</p>

# 📝 Contenido

- [📝 Contenido](#-contenido)
- [📦 Introducción](#-introducción)
- [🎨 Crear Flujos](#-crear-flujos)
- [Despliegue](#despliegue)
  - [Despliegue usando Google Cloud Platform](#despliegue-usando-google-cloud-platform)
  - [Despliegue en Railway](#despliegue-en-railway)
  - [Despliegue en Render](#despliegue-en-render)
- [🖥️ Interfaz de Línea de Comandos (CLI)](#️-interfaz-de-línea-de-comandos-cli)
  - [Uso](#uso)
    - [Variables de Entorno](#variables-de-entorno)
- [👋 Contribuir](#-contribuir)
- [🌟 Contribuidores](#-contribuidores)
- [📄 Licencia](#-licencia)

# 📦 Introducción

Puedes instalar Langflow con pip:

```shell
# Asegúrate de tener >=Python 3.10 instalado en tu sistema.
# Instala la versión pre-release (recomendada para las actualizaciones más recientes)
python -m pip install langflow --pre --force-reinstall

# o versión estable
python -m pip install langflow -U
```

Luego, ejecuta Langflow con:

```shell
python -m langflow run
```

También puedes ver Langflow en [HuggingFace Spaces](https://huggingface.co/spaces/Langflow/Langflow). [Clona el Space usando este enlace](https://huggingface.co/spaces/Langflow/Langflow?duplicate=true) para crear tu propio espacio de trabajo de Langflow en minutos.

# 🎨 Crear Flujos

Crear flujos con Langflow es fácil. Simplemente arrastra los componentes desde la barra lateral al espacio de trabajo y conéctalos para comenzar a construir tu aplicación.

Explora editando los parámetros del prompt, agrupando componentes y construyendo tus propios componentes personalizados (Custom Components).

Cuando hayas terminado, puedes exportar tu flujo como un archivo JSON.

Carga el flujo con:

```python
from langflow.load import run_flow_from_json

results = run_flow_from_json("ruta/al/flujo.json", input_value="¡Hola, Mundo!")
```

# Despliegue

## Despliegue usando Google Cloud Platform

Sigue nuestra guía paso a paso para desplegar Langflow en Google Cloud Platform (GCP) usando Google Cloud Shell. La guía está disponible en el documento [**Langflow en Google Cloud Platform**](https://github.com/langflow-ai/langflow/blob/dev/docs/docs/deployment/gcp-deployment.md).

Alternativamente, haz clic en el botón **"Abrir en Cloud Shell"** a continuación para iniciar Google Cloud Shell, clonar el repositorio de Langflow y comenzar un **tutorial interactivo** que te guiará a través del proceso de configuración de los recursos necesarios y despliegue de Langflow en tu proyecto GCP.

[![Abrir en Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/langflow-ai/langflow&working_dir=scripts/gcp&shellonly=true&tutorial=walkthroughtutorial_spot.md)

## Despliegue en Railway

Usa esta plantilla para desplegar Langflow 1.0 Preview en Railway:

[![Desplegar 1.0 Preview en Railway](https://railway.app/button.svg)](https://railway.app/template/UsJ1uB?referralCode=MnPSdg)

O esta para desplegar Langflow 0.6.x:

[![Desplegar en Railway](https://railway.app/button.svg)](https://railway.app/template/JMXEWp?referralCode=MnPSdg)

## Despliegue en Render

<a href="https://render.com/deploy?repo=https://github.com/langflow-ai/langflow/tree/dev">
<img src="https://render.com/images/deploy-to-render-button.svg" alt="Desplegar en Render" />
</a>

# 🖥️ Interfaz de Línea de Comandos (CLI)

Langflow proporciona una interfaz de línea de comandos (CLI) para una fácil gestión y configuración.

## Uso

Puedes ejecutar Langflow usando el siguiente comando:

```shell
langflow run [OPCIONES]
```

Cada opción se detalla a continuación:

- `--help`: Muestra todas las opciones disponibles.
- `--host`: Establece el host al que vincular el servidor. Se puede configurar usando la variable de entorno `LANGFLOW_HOST`. El valor predeterminado es `127.0.0.1`.
- `--workers`: Establece el número de procesos. Se puede configurar usando la variable de entorno `LANGFLOW_WORKERS`. El valor predeterminado es `1`.
- `--worker-timeout`: Establece el tiempo de espera del worker en segundos. El valor predeterminado es `60`.
- `--port`: Establece el puerto en el que escuchar. Se puede configurar usando la variable de entorno `LANGFLOW_PORT`. El valor predeterminado es `7860`.
- `--env-file`: Especifica la ruta al archivo .env que contiene variables de entorno. El valor predeterminado es `.env`.
- `--log-level`: Establece el nivel de registro. Se puede configurar usando la variable de entorno `LANGFLOW_LOG_LEVEL`. El valor predeterminado es `critical`.
- `--components-path`: Especifica la ruta al directorio que contiene componentes personalizados. Se puede configurar usando la variable de entorno `LANGFLOW_COMPONENTS_PATH`. El valor predeterminado es `langflow/components`.
- `--log-file`: Especifica la ruta al archivo de registro. Se puede configurar usando la variable de entorno `LANGFLOW_LOG_FILE`. El valor predeterminado es `logs/langflow.log`.
- `--cache`: Selecciona el tipo de caché a utilizar. Las opciones son `InMemoryCache` y `SQLiteCache`. Se puede configurar usando la variable de entorno `LANGFLOW_LANGCHAIN_CACHE`. El valor predeterminado es `SQLiteCache`.
- `--dev/--no-dev`: Alterna el modo de desarrollo. El valor predeterminado es `no-dev`.
- `--path`: Especifica la ruta al directorio frontend que contiene los archivos de compilación. Esta opción es solo para fines de desarrollo. Se puede configurar usando la variable de entorno `LANGFLOW_FRONTEND_PATH`.
- `--open-browser/--no-open-browser`: Alterna la opción de abrir el navegador después de iniciar el servidor. Se puede configurar usando la variable de entorno `LANGFLOW_OPEN_BROWSER`. El valor predeterminado es `open-browser`.
- `--remove-api-keys/--no-remove-api-keys`: Alterna la opción de eliminar las claves API de los proyectos guardados en la base de datos. Se puede configurar usando la variable de entorno `LANGFLOW_REMOVE_API_KEYS`. El valor predeterminado es `no-remove-api-keys`.
- `--install-completion [bash|zsh|fish|powershell|pwsh]`: Instala la función de autocompletar para el shell especificado.
- `--show-completion [bash|zsh|fish|powershell|pwsh]`: Muestra el código para la función de autocompletar para el shell especificado, permitiéndote copiar o personalizar la instalación.
- `--backend-only`: Este parámetro, con valor predeterminado `False`, permite ejecutar solo el servidor backend sin el frontend. También se puede configurar usando la variable de entorno `LANGFLOW_BACKEND_ONLY`.
- `--store`: Este parámetro, con valor predeterminado `True`, activa las funciones de la tienda, usa `--no-store` para desactivarlas. Se puede configurar usando la variable de entorno `LANGFLOW_STORE`.

Estos parámetros son importantes para los usuarios que necesitan personalizar el comportamiento de Langflow, especialmente en escenarios de desarrollo o despliegue especializado.

### Variables de Entorno

Puedes configurar muchas de las opciones de CLI usando variables de entorno. Estas se pueden exportar en tu sistema operativo o agregar a un archivo `.env` y cargarse usando la opción `--env-file`.

Se incluye un archivo de ejemplo `.env` llamado `.env.example` en el proyecto. Copia este archivo a un nuevo archivo llamado `.env` y reemplaza los valores de ejemplo con tus configuraciones reales. Si estás estableciendo valores tanto en tu sistema operativo como en el archivo `.env`, las configuraciones del `.env` tendrán prioridad.

# 👋 Contribuir

Aceptamos contribuciones de desarrolladores de todos los niveles para nuestro proyecto de código abierto en GitHub. Si deseas contribuir, por favor, consulta nuestras [directrices de contribución](./CONTRIBUTING.md) y ayuda a hacer que Langflow sea más accesible.

---

[![Historial de Estrellas](https://api.star-history.com/svg?repos=langflow-ai/langflow&type=Timeline)](https://star-history.com/#langflow-ai/langflow&Date)

# 🌟 Contribuidores

[![contribuidores de langflow](https://contrib.rocks/image?repo=langflow-ai/langflow)](https://github.com/langflow-ai/langflow/graphs/contributors)

# 📄 Licencia

Langflow se publica bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.
