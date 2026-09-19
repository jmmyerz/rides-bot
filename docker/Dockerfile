FROM python:3.11-alpine

# Default env
ENV TZ=America/Denver PATH=$PATH:/rides-bot PYTHONPATH=/rides-bot/src 
ENV RIDESBOT_SCHEDULER_RUN_AT="0 7 * * *" RIDESBOT_SCHEDULER_RUN_COMMAND="python3 -m rides_bot.app -ag9tn"

ENV SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/v0.2.49/supercronic-linux-amd64 \
    SUPERCRONIC_SHA1SUM=e63c11a9726b775a6a11801e81af4f3fb926aa68 \
    SUPERCRONIC=supercronic-linux-amd64

RUN apk add --no-cache python3 py3-pip py3-gunicorn git curl

# Install supercronic
RUN curl -fsSLO "$SUPERCRONIC_URL" \
    && echo "${SUPERCRONIC_SHA1SUM}  ${SUPERCRONIC}" | sha1sum -c - \
    && chmod +x "$SUPERCRONIC" \
    && mv "$SUPERCRONIC" "/usr/local/bin/${SUPERCRONIC}" \
    && ln -s "/usr/local/bin/${SUPERCRONIC}" /usr/local/bin/supercronic

# Copy entrypoint to root
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy the application code (will also be synced on each container start)
RUN git clone https://github.com/jmmyerz/rides-bot.git /rides-bot

# Install requirements
RUN pip3 install --no-cache-dir -r /rides-bot/requirements.txt

# Set command- defines the role of the container (passed to the entrypoint)
# default: scheduler, options: scheduler (supercronic), listener[discord, groupme, telegram], debug
CMD ["scheduler"]

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]