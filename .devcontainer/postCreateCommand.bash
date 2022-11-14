#!/bin/bash

set -e

cd "$(dirname "$0")/.."


pip3 install --no-cache-dir -r ./requirements.txt
pip3 install --no-cache-dir -r ./klyqa_ctl/requirements.txt