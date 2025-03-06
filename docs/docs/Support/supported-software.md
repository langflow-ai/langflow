---
title: Supported software versions
slug: /support-supported-software
---

Support covers only the following software versions for Langflow.

Last updated: 2025-03-06

## Core Information
- **Langflow Version**: 1.2.0
- **Python Version Required**: >=3.10,<3.14

## Main Dependencies

### Integration
| Package | Version |
| ------- | ------- |
| google-api-python-client | ==2.154.0 |
| google-search-results | ≥2.4.1,<3.0.0 |

### Other
| Package | Version |
| ------- | ------- |
| langflow-base | ==0.2.0 |

### Utils
| Package | Version |
| ------- | ------- |
| beautifulsoup4 | ==4.12.3 |

## Optional Dependencies

### deploy
| Package | Version |
| ------- | ------- |
| celery[redis | any |

### local
| Package | Version |
| ------- | ------- |
| llama-cpp-python | ≈0.2.0 |
| sentence-transformers | ≥2.3.1 |
| ctransformers | ≥0.2.10 |

### couchbase
| Package | Version |
| ------- | ------- |
| couchbase | ≥4.2.1 |

### cassio
| Package | Version |
| ------- | ------- |
| cassio | ≥0.1.7 |

### postgresql
| Package | Version |
| ------- | ------- |
| sqlalchemy[postgresql_psycopg2binary | any |

### connect
| Package | Version |
| ------- | ------- |
| clickhouse-connect | ==0.7.19 |

### ingest
| Package | Version |
| ------- | ------- |
| nv-ingest-client | ==2025.2.7.dev0 |
| python-pptx | ==0.6.23 |
| pymilvus[bulk_writer,model | any |