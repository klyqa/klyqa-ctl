#!/bin/bash

set -ex
(d="dist.org/$(date +%Y%m%d_%H%M%S)"
mkdir -vp "$d"
mv dist/ $d)

python3.9 setup.py sdist

# create virtual python environment for testing installing the package
# and tetsing the package
target=$(cd dist && ls *.tar.gz)
rm -rf package.test.venv
mkdir package.test.venv
cp dist/$target package.test.venv
(
python3 -m venv package.test.venv
cd package.test.venv/
source ./bin/activate
echo "install klyqa ctl package ..."
python3.9 -m pip install $target
echo "test klyqa ctl package module ..."
python3.9 -m klyqa_ctl
)


gpg --detach-sign -a dist/*.tar.gz

twine upload --repository-url https://test.pypi.org/legacy/ dist/*.tar.gz dist/*.asc --verbose
twine upload  dist/*.tar.gz dist/*.asc
