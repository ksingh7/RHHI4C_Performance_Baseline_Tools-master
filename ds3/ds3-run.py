#!/bin/python

# script to run the benchmarks against ds2 / ds3 stacks mostly automatically
# call logic:
# ./run_bench.py --stacks <number_of_stacks> --ds2 <number_of_ds2_containers> --ds3 <nr_of_ds3_containers> -id <identifier>
# The containers will run with a consecutively increasing number which will be used to identify their specific DriverConfig.txt file
# container 0 will use  DriverConfig.txt.0 to map it into the container etc. 

import sys
import MySQLdb
import time
import datetime
import commands
import json
import urllib2
import re
import getopt
import subprocess
import uuid
import socket
import os

hostname = socket.getfqdn()
processes = dict()
c_counter = 1 # containercounter
populate = 0

def get_threads():
    # we can rely on DriverConfig.txt.0 to be there since we need to run at least one container
    # if it is not, we bail out
    try:
        fh = open('ds3webdriver/DriverConfig.txt.server-' + str(c_counter))
    except: 
        print "Unable to open" + ' ds3webdriver/DriverConfig.txt.server-' + str(c_counter) + " exiting"
        sys.exit(1)

    for line in fh:
        if "n_threads" in line: 
            threads = (line.split("="))[1]
        if "db_size" in line:
            db_size = (line.split("="))[1]
        if "run_time" in line:
            global run_time
            run_time = (line.split("="))[1]
            
    fh.close
    return threads, db_size, run_time

def myconverter(o):
    if isinstance(o, datetime.datetime):
        return o.__str__()

def ds2_subp():
     global c_counter
     typ = "ds2"
     cmd = 'docker run -t -v ds3webdriver/DriverConfig.txt.server-' + str(c_counter) + ':/opt/app-root/app/driver_config.ini:Z dmesser/ds2mysqldriver:latest'
     proc = (subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE))
     processes[proc] = typ
     c_counter += 1

def ds3_subp():
     global c_counter
     cwd = os.getcwd()
     typ = "ds3"
     cmd = 'docker run -t -v ' + cwd + '/ds3webdriver/DriverConfig.txt.server-' + str(c_counter) + ':/opt/app-root/app/driver_config.ini:Z dmesser/ds3webdriver:latest' 
     print cmd
     proc = (subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE))
     processes[proc] = typ
     c_counter += 1

def updatedb(result, typ, conn, stacks, threads, uid, idstring, db_size):
    global populate
    if populate == 1:
       print "Not updating the DB since this is a population run"
       return 1

    #print "Running updatedb"
    for line in result.split("\n"):
       if "Final" in line:
           values = line.split()

           # Prepare the values so they fit into the db fields
           year = (values[1].split("/"))[2]
           day = (values[1].split("/"))[1]
           month = re.sub('[(]', '', (values[1].split("/"))[0])
           time = re.sub('[:)]', '', values[2])
           test_date = year + month + day + time
           et = values[4]
           n_overall = (values[5].split("="))[1]
           opm = (values[6].split("="))[1]
           rt_tot_lastn_max = (values[7].split("="))[1]
           rt_tot_avg = (values[8].split("="))[1]
           n_login_overall=(values[9].split("="))[1]
           n_newcust_overall=(values[10].split("="))[1]
           n_browse_overall=(values[11].split("="))[1]
           n_purchase_overall=(values[12].split("="))[1]
           rt_login_avg_msec=(values[13].split("="))[1]
           rt_newcust_avg_msec=(values[14].split("="))[1]
           rt_browse_avg_msec=(values[15].split("="))[1]
           rt_purchase_avg_msec=(values[16].split("="))[1]
           rt_tot_sampled=(values[17].split("="))[1]
           n_rollbacks_overall=(values[18].split("="))[1]
           rb_rate=values[21]
           rollback_rate = re.sub('[%]', '', rb_rate)
           #print "dstyp: ", typ
           #print "test_date: ", test_date
           #print "et: ", et
           #print "n_overall: ", n_overall
           #print "opm: ", opm
           #print "rt_tot_lastn_max: ", rt_tot_lastn_max
           #print "rt_tot_avg: ", rt_tot_avg
           #print "n_login_overall: ", n_login_overall
           #print "n_newcust_overall: ", n_newcust_overall
           #print "n_browse_overall: ", n_browse_overall
           #print "n_purchase_overall: ", n_purchase_overall
           #print "rt_login_avg_msec: ", rt_login_avg_msec
           #print "rt_newcust_avg_msec: ", rt_newcust_avg_msec
           #print "rt_browse_avg_msec: ", rt_browse_avg_msec
           #print "rt_purchase_avg_msec: ", rt_purchase_avg_msec
           #print "rt_tot_sampled: ", rt_tot_sampled
           #print "n_rollbacks_overall: ", n_rollbacks_overall
           #print "rollback_rate: ", rollback_rate

           # Insert the results into the DB
           x = conn.cursor()
           #print "Entering data into mysql"
           try:
               x.execute("""INSERT INTO results (hostname, idstring, uuid, db_size, test_date, threads, nr_stacks, et, n_overall, ds_typ, opm, rt_tot_lastn_max, rt_tot_avg, n_login_overall, n_newcust_overall, n_browse_overall, rt_login_avg_msec, rt_newcust_avg_msec, rt_browse_avg_msec, rt_purchase_avg_msec, n_purchase_overall,  rt_tot_sampled, n_rollbacks_overall, rollback_rate) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", (hostname, idstring, uid, db_size, test_date, threads, stacks, et, n_overall, typ, opm, rt_tot_lastn_max, rt_tot_avg, n_login_overall, n_newcust_overall, n_browse_overall, rt_login_avg_msec, rt_newcust_avg_msec, rt_browse_avg_msec, rt_purchase_avg_msec, n_purchase_overall, rt_tot_sampled, n_rollbacks_overall, rollback_rate))                                 
               conn.commit()
               print "DB commit successful"
           except MySQLdb.Error as e:
               print "Error: ", e
               conn.rollback()

def main(argv):

    stacks = '0'
    ds2 = 0
    ds3 = 0
    idstring = ''
    uid = 'no uuid given'
    global populate

    try:
        opts, args = getopt.getopt(argv,"hs:d:e:i:u:p",["stacks=","ds2=","ds3=","id=", "uuid=", "populate"])
    except getopt.GetoptError:
        print 'getopt_error: run_bench.py -s <stacks> -d <ds2_instances> -e <ds3_instances> -i <idstring> -p'
        sys.exit(2)
    # validating command line options
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print 'run_bench.py -s <stacks> -d <ds2_instances> -e <ds3_instances> -i <idstring> -u <uuid> -p'
            sys.exit()
        elif opt in ("-s", "--stacks"):
            stacks = arg
            if stacks == 0:
                print "No stack number given, exiting."
                sys.exit(1)
        elif opt in ("-d", "--ds2"):
            ds2 = arg
        elif opt in ("-e", "--ds3"):
            ds3 = arg
            if (ds2 == 0 and ds3 ==0):
                print "At least one ds2 or ds3 container need to run and both are set to 0, exiting"
                sys.exit(1)
        elif opt in ("-p", "--populate"):
            populate = 1      
        elif opt in ("-i", "--id"):
            idstring = arg
            if idstring == '' and populate == 0:
                print "No identification string given, exiting"
                sys.exit(1)
        elif opt in ("-u", "--uuid"):
            uid = arg

    # get the number of threads
    threads, db_size, run_time = get_threads()

    # flush caches
    
    #print "Flushing local caches"
    #os.system("echo 3 > /proc/sys/vm/drop_caches")
    print "Flushing Hypervisor caches"
    os.system("ssh -t heat-admin@192.168.120.6 'echo 3 | sudo tee /proc/sys/vm/drop_caches'")
    os.system("ssh -t heat-admin@192.168.120.14 'echo 3 | sudo tee /proc/sys/vm/drop_caches'")

    # Set up the DB connection
    try:
        conn = MySQLdb.connect(host= "localhost", user="ds3-results", passwd="ds3-results", db="ds3_results")
        print "Database connection succesfully established"
    except:
        print "No connection to the DB server"
        exit(0)

    # set the start date
    starttime = int(time.time() * 1000) + int(1.5 * 60 * 1000)
    #starttime = int(time.time() * 1000) + (int(run_time) * 60 * 1000)
#    time.sleep(10)
    uid = str(uuid.uuid4())
    # run the docker instance(s) and collect the output 
    #for i in range(0, int(ds2)):
    #    print "Starting ds2 container number ", i
    #    ds2_subp()
    for j in range (0, int(ds3)):
        print "Starting ds3 container number ", j
        ds3_subp()

    for key in processes:
        #print key, processes[key]
        key.wait()
        result = (key.communicate())[0]
        typ = (processes[key])
        updatedb(result, typ, conn, stacks, threads, uid, idstring, db_size)
        #global endtime
        #endtime = int(time.time() * 1000)

    print "All docker instances finished"
    print "Adding annotation to grafana "
    #endtime = int(time.time() * 1000) + int(3 * 60 * 1000)
    #endtime = int(time.time() * 1000) + ((int(run_time) + 1) * 60 * 1000)
    endtime = starttime + ((int(run_time) + 2) * 60 * 1000)
    cmd = 'curl -X POST http://admin:root123@172.21.1.175:3000/api/annotations -H "Content-Type: application/json" -d \'{"time":' + str(starttime) + ',"isRegion":true,"timeEnd":' + str(endtime) + ',"tags":["' + idstring + '", "ds3"],"text":"' + idstring + '"}\''

    result = commands.getoutput(cmd)
    print "Grafana Annotation done"

    # close the DB connection
    conn.close

if __name__ == "__main__":
   try:
      arg = sys.argv[1]
   except IndexError:
      print "Usage: run_bench.py -s <stacks> -d <ds2_instances> -e <ds3_instances> -i <id_string> -u <uuid> -p"
      sys.exit()

   main(sys.argv[1:])

