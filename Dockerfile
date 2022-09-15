FROM python:3.9-slim

ADD klyqa-ctl.py /
ADD requirements.txt /

RUN apk add --no-cache tzdata
ENV TZ=Europe/Berlin

RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["/bulb_cli.py"]
