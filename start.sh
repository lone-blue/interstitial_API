#!/bin/bash

# Load the .env file if it exists
if [ -f .env ]; then
  source .env
fi

# Default values, used if not set in the .env file
LOCAL_PORT=${LOCAL_PORT:-3456}
DESTINATION_API=${DESTINATION_API:-"http://localhost:6789"}
PROMPT_INJECTOR=${PROMPT_INJECTOR:-""}
MESSAGE_PREFIX=${MESSAGE_PREFIX:-"\\n\\n Instruction:\\n"}
MESSAGE_SUFFIX=${MESSAGE_SUFFIX:-"\\n\\n Response:\\n"}
USE_NOHUP=false
RELOAD=false
WAN_ENABLED=false
HOST=0.0.0.0

# Parse command-line options
while [ "$#" -gt 0 ]; do
  case "$1" in
    --port)
      LOCAL_PORT="$2"
      shift 2
      ;;
    --api-url)
      DESTINATION_API="$2"
      shift 2
      ;;
    --prefix)
      MESSAGE_PREFIX="$2"
      shift 2
      ;;
    --suffix)
      MESSAGE_SUFFIX="$2"
      shift 2
      ;;
    --prompter)
      PROMPT_INJECTOR="$2"
      shift 2
      ;;
    --host)
      WAN_ENABLED=true
      HOST="$2"
      shift 2
      ;;
    --nohup)
      USE_NOHUP=true
      shift
      ;;
    --reload)
      RELOAD=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

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