#!/bin/bash
mkdir -p /tmp/cbt/log
for i in $(seq $1 $2); do
   echo "*************** Starting Test-$i ***************"
   ./cbt.py -a karans-workbench/output/rb-write-read-4m-4k-$i-client karans-workbench/rb-write-read-4m-4k-$i-client.yaml > /tmp/cbt/log/rb-write-read-4m-4k-$i-client.yaml 2>&1
   echo "*************** Test-$i completed ***************"
   sleep 120 
done
