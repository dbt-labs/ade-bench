#!/bin/bash
## Remove the using_department variable and disable package models,
## then copy replacement staging models
mkdir -p models/staging
patch -p1 < /sage/solutions/changes.patch
