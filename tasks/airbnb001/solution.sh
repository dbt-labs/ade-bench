#!/bin/bash

## Replace all surrogate_key functions with generate_surrogate_key
patch -p1 < /sage/solutions/changes.patch
