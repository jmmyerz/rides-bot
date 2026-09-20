#!/bin/sh
#
# Entrypoint script for the rides-bot container
# Determines the role of the container based on the CMD argument
#
# Usage:
#   docker run rides-bot [scheduler|listener[discord|groupme|telegram]|debug]
#
# Roles:
#   scheduler - runs the supercronic scheduler
#   listener  - runs the bot listener (discord, groupme, telegram)
#   debug     - runs the container in debug mode (sleeps indefinitely so you can attach and debug)
#
set -e

if [ "$REWRITE_ENTRYPOINT" = "true" ]; then
    cp /rides-bot/docker/entrypoint.sh /entrypoint.sh
    chmod +x /entrypoint.sh
    echo "Rewritten entrypoint script to /entrypoint.sh"
    exec /entrypoint.sh "$@"
fi

# Sync the /rides-bot repo
if [ -d "/rides-bot/.git" ]; then
    echo "Syncing /rides-bot repository..."
    cd /rides-bot
    git pull origin master > /tmp/git_pull.log 2>&1 || { cat /tmp/git_pull.log; exit 1; }
fi

# Check the hash of this file (/entrypoint.sh) against the committed version in the repository
# If the hash has changed, assume we should run the repo version
if [ -f "/rides-bot/docker/entrypoint.sh" ]; then
    REPO_HASH=$(sha256sum /rides-bot/docker/entrypoint.sh | awk '{print $1}')
    CURRENT_HASH=$(sha256sum /entrypoint.sh | awk '{print $1}')
    if [ "$REPO_HASH" != "$CURRENT_HASH" ]; then
        echo "Entrypoint script has changed in the repository. Using the repo version."
        chmod +x /rides-bot/docker/entrypoint.sh
        exec REWRITE_ENTRYPOINT=true /rides-bot/docker/entrypoint.sh "$@"
    fi
fi

# Determine the role of the container based on the first argument
ROLE="${1:-scheduler}"

# If the role is listener, set the listener type based on the second argument or exit if not provided
if [ "$ROLE" = "listener" ]; then
    LISTENER_TYPE="${2:-}"
    if [ -z "$LISTENER_TYPE" ]; then
        echo "Listener type not provided"
        exit 1
    fi
fi

# If role is "listener groupme", set ROLE to "groupme"
if [ "$ROLE" = "listener" ] && [ "$LISTENER_TYPE" = "groupme" ]; then
    ROLE="groupme"
fi

# Echo the role (and optionally the listener type if applicable) alongside the PID
echo "Starting container with role: $ROLE${LISTENER_TYPE:+, listener type: $LISTENER_TYPE}, PID: $$"

# Ensure the requirements are installed
echo "Installing Python requirements..."
pip3 install --no-cache-dir -r /rides-bot/requirements.txt > /tmp/pip_install.log 2>&1 || { cat /tmp/pip_install.log; exit 1; }

# If role is scheduler, run supercronic against /rides-bot/scheduler_check and wait up to 10s to see a line with "Scheduler check requested... hello from rides-bot!"
# If this fails, echo the contents of the log and exit with an error, if it succeeds, write the cronfile from RIDESBOT_SCHEDULER_RUN_AT and RIDESBOT_SCHEDULER_RUN_COMMAND
if [ "$ROLE" = "scheduler" ]; then
    echo "Running scheduler check..."
    supercronic /rides-bot/scheduler_check > /tmp/scheduler_check.log 2>&1 &
    CHECK_PID=$!
    timeout 10 sh -c 'until grep -q "Scheduler check requested... hello from rides-bot!" /tmp/scheduler_check.log; do sleep 1; done' || { cat /tmp/scheduler_check.log; kill $CHECK_PID; exit 1; }
    kill $CHECK_PID
    echo "$RIDESBOT_SCHEDULER_RUN_AT $RIDESBOT_SCHEDULER_RUN_COMMAND" > /cronfile
fi

case "$ROLE" in
    scheduler)
        echo "Scheduler running with TZ: $TZ, current time: $(date)"
        exec supercronic /cronfile
        ;;
    groupme)
        echo "Starting GroupMe listener..."
        cd /rides-bot/src
        exec gunicorn -w 4 -b 0.0.0.0:8000 rides_bot.callback_server:app
        ;;
    listener)
        echo "Starting $LISTENER_TYPE listener..."
        exec python3 /rides-bot/src/rides_bot/"$LISTENER_TYPE"_listener.py
        ;;
    debug)
        echo "Starting container in debug mode..."
        exec sleep infinity
        ;;
    *)
        echo "Unknown role: $ROLE"
        exit 1
        ;;
esac