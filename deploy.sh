. ./env.sh
#docker build -t splitgraph-chatgpt-plugin .
#gcloud builds submit --tag gcr.io/splitgraph-chatgpt-plugin/splitgraph-chatgpt-plugin
gcloud builds submit --config cloudbuild.json .
gcloud run deploy splitgraph-chatgpt-plugin \
    --image gcr.io/splitgraph-chatgpt-plugin/splitgraph-chatgpt-plugin \
    --add-cloudsql-instances "splitgraph-chatgpt-plugin:us-central1:embeddingstore2" \
    --set-env-vars PG_CONN_STR="$PG_CONN_STR" \
    --set-env-vars INSTANCE_CONNECTION_NAME="$INSTANCE_CONNECTION_NAME" \
    --set-env-vars DB_NAME="$DB_NAME" \
    --set-env-vars DB_USER="$DB_USER" \
    --set-env-vars DB_PASS="$DB_PASS" \
    --set-env-vars OPENAI_API_KEY="$OPENAI_API_KEY" \
    --set-env-vars OAUTH_GOOGLE_CLIENT_ID="$OAUTH_GOOGLE_CLIENT_ID" \
    --set-env-vars OAUTH_GOOGLE_SECRET="$OAUTH_GOOGLE_SECRET" \
    --set-env-vars OAUTH_OPENAI_CLIENT_ID="$OAUTH_OPENAI_CLIENT_ID" \
    --set-env-vars OAUTH_OPENAI_SECRET="$OAUTH_OPENAI_SECRET" \
    --set-env-vars OAUTH_PLUGIN_JWT_SECRET="$OAUTH_PLUGIN_JWT_SECRET" \
    --region="us-central1" \
    --service-account="chatgpt-plugin-service@splitgraph-chatgpt-plugin.iam.gserviceaccount.com" \
    --max-instances=1 \
    --allow-unauthenticated
