#!/bin/bash
(d="dist.org/$(date +%Y%m%d_%H%M%S)" && \
mkdir -vp "$d" && \
mv dist/ $d)
python3 setup.py sdist && \
gpg --detach-sign -a dist/*.tar.gz && \
twine upload --repository-url https://test.pypi.org/legacy/ dist/*.tar.gz dist/*.asc --verbose && \
twine upload  dist/*.tar.gz dist/*.asc
