FROM --platform=linux/amd64 python:3.10.13-alpine3.19

ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache bash sqlite-dev

RUN addgroup -S nonroot \
	&& adduser -S -D -s /bin/bash -G nonroot nonroot

USER nonroot
WORKDIR /app

COPY --chown=nonroot:nonroot ./requirements.txt ./requirements.txt
RUN pip install --no-warn-script-location --upgrade pip
RUN pip install --no-warn-script-location --no-cache-dir -r ./requirements.txt \
	&& rm ./requirements.txt

COPY --chown=nonroot:nonroot . .

RUN chmod u+x ./start.sh

CMD ["./start.sh"]
