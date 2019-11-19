#!/bin/bash
for i in 1 2 3
  do 
    test=14
    run=$i
    touch log.output
    > log.output

    for count in {10..1}
      do 
        #sudo python ds-run.py --stacks 1 --ds3 $count --id test_"$test"_run_"$run"_stack_"$count" &> log.output  
        sudo python ds-run.py --stacks 1 --ds2 $count --id test_"$test"_run_"$run"_stack_"$count" &> log.output  
        sleep 60;
    done
 sleep 300;
done
