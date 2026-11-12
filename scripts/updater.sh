#!/bin/sh

# Install curl and jq
apk add --no-cache curl jq > /dev/null 2>&1

echo "Waiting 30 seconds for Lavalink to boot..."
sleep 30

API="http://host.docker.internal:2333/youtube"
AUTH="Authorization: youshallnotpass"
TYPE="Content-Type: application/json"

while true; do
  echo "Fetching fresh PO token from provider..."
  
  # Fetch raw JSON from the provider
  RAW_JSON=$(curl -s -X POST http://pot-provider:4416/get_pot \
    -H "Content-Type: application/json" \
    -d "{}")
  if [ -z "$RAW_JSON" ] || [ "$RAW_JSON" = "null" ]; then
    echo "Provider returned empty response. Retrying in 10 seconds..."
    sleep 10
    continue
  fi

  # Map provider's 'contentBinding' to Lavalink's required 'visitorData' key
  PAYLOAD=$(echo "$RAW_JSON" | jq -c '{poToken: .poToken, visitorData: .contentBinding}')
  
  echo "Mapped Payload for Lavalink: $PAYLOAD"
  echo "Pushing to Lavalink..."
  
  # Push to Lavalink
  curl -i -X POST "$API" -H "$AUTH" -H "$TYPE" -d "$PAYLOAD"
  
  echo ""
  echo "Sleeping for 30 minutes..."
  sleep 1800
done
