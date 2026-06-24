#!/usr/bin/env bash
# Deploy the two MCP servers to Google Cloud Run (assignment §6 stage-2 / §7).
#
# Prereqs (run once, with YOUR Google login — these bill your account):
#   gcloud auth login
#   gcloud config set project <YOUR_PROJECT_ID>
#
# Then:  bash deploy/cloudrun.sh
#
# What it does: enables the APIs, mints a shared bearer token (unless you pass
# one), builds the image in the cloud (no local Docker), and deploys a cop + a
# thief service. Network access is open but every tool requires the bearer token
# (MCP_AUTH_TOKEN), so the servers are NOT unprotected (§7). Revoke later by
# re-running with a new token, or `gcloud run services delete`.
set -euo pipefail

REGION="${REGION:-me-west1}"                 # Tel Aviv; override e.g. REGION=europe-west1
COP_SERVICE="${COP_SERVICE:-cop-thief-cop}"
THIEF_SERVICE="${THIEF_SERVICE:-cop-thief-thief}"
# Reuse a token if provided, else generate a strong one and save it locally.
TOKEN="${MCP_AUTH_TOKEN:-$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')}"
# If an OpenAI key is in the environment, inject it so server-side play_turn can use
# the LLM (config llm.provider=openai). Accepts the standard name or this repo's
# OPEN_API_KEY. Injected at deploy time only — never baked into the image (.dockerignore).
OPENAI_KEY="${OPENAI_API_KEY:-${OPEN_API_KEY:-}}"

PROJECT="$(gcloud config get-value project 2>/dev/null)"
[ -n "$PROJECT" ] || { echo "No project set. Run: gcloud config set project <ID>"; exit 1; }
echo ">> Project: $PROJECT   Region: $REGION"

echo ">> Enabling Cloud Run + Cloud Build APIs..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com

deploy_role () {  # $1=service  $2=role
  echo ">> Deploying $1 (role=$2)..."
  local env_vars="MCP_ROLE=$2,MCP_AUTH_TOKEN=$TOKEN"
  [ -n "$OPENAI_KEY" ] && env_vars="$env_vars,OPENAI_API_KEY=$OPENAI_KEY"
  gcloud run deploy "$1" \
    --source . \
    --region "$REGION" \
    --allow-unauthenticated \
    --max-instances=1 \
    --set-env-vars "$env_vars"
}

deploy_role "$COP_SERVICE"   cop
deploy_role "$THIEF_SERVICE" thief

COP_URL="$(gcloud run services describe "$COP_SERVICE" --region "$REGION" --format='value(status.url)')"
THIEF_URL="$(gcloud run services describe "$THIEF_SERVICE" --region "$REGION" --format='value(status.url)')"

cat <<EOF

============================================================
Deployed. MCP endpoints (append /mcp):
  COP    : ${COP_URL}/mcp
  THIEF  : ${THIEF_URL}/mcp
Bearer token (share out of band; this is your MCP_AUTH_TOKEN):
  ${TOKEN}

Smoke-test from this machine:
  .venv/bin/cop-thief peer-check ${COP_URL}/mcp --token ${TOKEN}

Mandatory cloud self-play run (LLM stays local, Approach 1):
  COP_MCP_URL=${COP_URL}/mcp THIEF_MCP_URL=${THIEF_URL}/mcp \\
  MCP_AUTH_TOKEN=${TOKEN} .venv/bin/cop-thief run --mcp

Put these four into config.yaml team.* / report for the §9.x report when ready.
============================================================
EOF
