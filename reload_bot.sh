# Check if the script is being run as root
if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

# Set pwd to the directory of this script and run `gh repo sync`
# to update the bot with the latest changes from the repository.
cd "$(dirname "$0")" || exit
gh repo sync

# Find the gunicorn process that is running rides_bot.callback_server:app and kill it
# Need to kill the main thread and the worker threads
pkill -f "rides_bot.callback_server:app"

# Restart the discord_listener and telegram_listener services
systemctl restart discord_listener
systemctl restart telegram_listener

# Restart the callback_server service
# Need to add this script's directory to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$PWD
gunicorn rides_bot.callback_server:app -b 127.0.0.1:7045 &

# Get the status of the services and print them
systemctl status discord_listener
systemctl status telegram_listener

# Get the status of the callback_server and print it
ps aux | grep "rides_bot.callback_server:app"

# Fin
echo "Bot has been reloaded."

exit 0