#!/usr/bin/bash

docker build -t penai .

docker run -it --rm --shm-size=1g -v "$(pwd)":/workspaces/penai penai
