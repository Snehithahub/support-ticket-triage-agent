#!/bin/sh
# One-shot init for the n8n container: import the TriageDesk workflow into n8n's data volume
# and publish (activate) it, so the production webhook /webhook/ticket is live when n8n starts.
#
# Re-runnable: n8n 2.x refuses to re-import over a published workflow ("permission to deactivate"),
# so an existing copy is unpublished first. Import then upserts by workflow id and we publish again.
# (import:workflow --activeState=fromJson only works in queue/multi-main mode, hence publish:workflow.)
set -eu

WORKFLOW_FILE="${WORKFLOW_FILE:-/workflows/workflows/triage.json}"
WORKFLOW_ID="${WORKFLOW_ID:-TriageDeskIntake}"

if n8n list:workflow 2>/dev/null | grep -q "^${WORKFLOW_ID}|"; then
  echo "unpublishing existing workflow ${WORKFLOW_ID} before re-import"
  n8n unpublish:workflow --id="${WORKFLOW_ID}"
fi

echo "importing ${WORKFLOW_FILE}"
n8n import:workflow --input="${WORKFLOW_FILE}"

echo "publishing workflow ${WORKFLOW_ID}"
n8n publish:workflow --id="${WORKFLOW_ID}"

n8n list:workflow
