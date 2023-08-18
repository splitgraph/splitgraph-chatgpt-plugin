# splitgraph-chatgpt-plugin
A ChatGPT plugin for searching the Splitgraph Data Delivery Network using natural language questions.

# Installation
```bash
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

# Running tests
```bash
python -m unittest
```

# Running the plugin locally
```bash
OPENAI_API_KEY="sk-..." PG_CONN_STR='postgresql://...' python3 -m server.main
```
