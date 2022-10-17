FROM python:3.9-alpine
# -slim


ADD .git /.git

RUN apk add --no-cache tzdata
ENV TZ=Europe/Berlin

RUN apk add --no-cache bash git gcc libc-dev bash-completion coreutils nano gpg

ADD klyqa_ctl /klyqa_ctl
RUN ls -a 
RUN pip install --no-cache-dir -r klyqa_ctl/requirements.txt
RUN xargs -n1 -P16 pip3 install < <(sed '/#.*/d' /klyqa_ctl/requirements.txt)
ENTRYPOINT ["/klyqa_ctl/klyqa_ctl.py"]
