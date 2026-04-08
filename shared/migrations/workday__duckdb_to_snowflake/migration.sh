#!/bin/bash
patch -p1 < "$(dirname "$(readlink -f "${BASH_SOURCE}")")/migration.patch"
