#!/bin/bash

# Load the .env file if it exists
if [ -f .env ]; then
  source .env
fi

# Default values, overridden with pre-determined values
LOCAL_PORT=3456
DESTINATION_API="http://localhost:6789"
PROMPT_INJECTOR="user"
MESSAGE_PREFIX="\n\n### User:\n"
MESSAGE_SUFFIX="\n\n### Assistant:\n"
USE_NOHUP=true
RELOAD=false # warning, enabling reload will eat up a lot of CPU time
WAN_ENABLED=true
HOST=0.0.0.0

# Export the environment variables
export DESTINATION_API
export MESSAGE_PREFIX
export MESSAGE_SUFFIX
export PROMPT_INJECTOR

# Build the command to launch Uvicorn
COMMAND="uvicorn interstitial_API:app --port $LOCAL_PORT"

# If host parameter set, modify the command
if [ "$WAN_ENABLED" = true ]; then
  COMMAND="$COMMAND --host $HOST"
fi

# If reload is requested, modify the command
if [ "$RELOAD" = true ]; then
  COMMAND="$COMMAND --reload"
fi

# If nohup is requested, modify the command
if [ "$USE_NOHUP" = true ]; then
  COMMAND="nohup $COMMAND > /dev/null 2>&1 &"
fi

# Execute the command
eval $COMMAND
