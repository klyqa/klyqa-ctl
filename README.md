# Klyqa device control client

A commandline client for controlling your Klyqa devices.

Using your klyqa account or dev mode for bulbs onboarded in dev mode.

# Install via pypi:
`pip install klyqa-ctl`

Use then as module `import klyqa_ctl` or on the

# Commandline
```$ klyqa-ctl ...```


# Git Repository

You can also clone this repository.

You can run the python script directly with

```
./klyqa_ctl/klyqa_ctl.py
```

Use pip for installation of required dependency packages.

```
pip install -r requirements.txt
```

Tested and developed with Python v3.9.

or build it as docker container.

## Build docker python script container

Build docker container for automatic required dependency download and easy handling from within the project folder.

`docker build -t klyqa_ctl .`

## Run docker python script container

`docker run --net=host --rm -it klyqa_ctl`

or to keep the container running:

`docker run --net=host --name=klyqa_ctl --entrypoint=python3 -itd klyqa_ctl`

and then do a:

`docker exec klyqa_ctl python3 /bulb_cli.py`

## Debug mode

If you want more logging verbosity

`--debug`

## Help with all commands

`--help`

## Interactive client

If you provide no bulb unit id and/or a command to send, the bulb discovery and selection will be shown and afterwards a command prompt.

### Use klyqa user account

Add username and password to the arguments

```
--username <emailaddress> --password <password>
```

### Hosts

Use production (default) or test host.

```
--prod or --test
```

## Local Mode

```klyqa-ctl --aes 00112233445566778899AABBCCDDEEFF --bulb_unitids db60e93f99```

### Connection types

tryLocalThanCloud (Default) for sending the command

```
--tryLocalThanCloud
```

Use

```
--local
```

for local only connection

Use

```
--cloud
```

for cloud only connection

### Examples commands

Send request

```
--request
```

Setting color rgb

```
--color r g b
```

Selecting bulbs directly by unit ids seperated by commas ","

```
--bulb_unitids <bulb-unitid1>,<bulb-unitid2>,...
```

Scenes

```
--party, --TVtime, --fireplace, ...
```

### Use dev env

For running the bulbs in the development configuration locally without a klyqa account and with the default development AES key.

```
--dev
```
