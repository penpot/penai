#!/usr/bin/bash

docker build -t penai .

docker run -it --rm -v "$(pwd)":/workspace penai