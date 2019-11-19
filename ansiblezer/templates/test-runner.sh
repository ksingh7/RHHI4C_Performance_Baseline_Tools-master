#!/bin/bash
test=5
run=6

touch log.output
> log.output

for count in {1..1}
 do 
  sudo python ds3-run.py --stacks 1 --ds3 $count --id test_"$test"_run_"$run"_stack_"$count" &> log.output  
 sleep 60;
done
