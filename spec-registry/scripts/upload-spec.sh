#!/usr/bin/env bash
# Upload an API spec file to the spec registry S3 bucket.
#
# Usage: ./upload-spec.sh <local-file> <n8n-node-name> [bucket] [prefix]
#
# The file is uploaded with the naming convention used by the spec registry:
#   <n8n-node-name>.json  (or .yaml/.yml based on the source extension)
#
# Examples:
#   ./upload-spec.sh slack-api.json n8n-nodes-base.Slack
#   ./upload-spec.sh github.yaml n8n-nodes-base.Github my-bucket specs/
set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <local-file> <n8n-node-name> [bucket] [prefix]" >&2
    exit 1
fi

LOCAL_FILE="$1"
NODE_NAME="$2"
BUCKET="${3:-phaeton-spec-registry}"
PREFIX="${4:-specs}"

if [[ ! -f "$LOCAL_FILE" ]]; then
    echo "Error: file not found: $LOCAL_FILE" >&2
    exit 1
fi

# Preserve original extension
EXT="${LOCAL_FILE##*.}"
S3_KEY="${PREFIX:+${PREFIX}/}${NODE_NAME}.${EXT}"

echo "Uploading ${LOCAL_FILE} -> s3://${BUCKET}/${S3_KEY}"
aws s3 cp "$LOCAL_FILE" "s3://${BUCKET}/${S3_KEY}"
echo "Done."
