#!/bin/bash

set -ex

# This script needs to be run once

# Kill a potential old server
wineserver -k || true

# Start a new server
wineserver -p || true

# Run a process to start up all background wine processes
wine64 wineboot || true

