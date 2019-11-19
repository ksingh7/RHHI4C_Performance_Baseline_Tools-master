#!/usr/bin/python
#
# fio-get-lat-iops.py - example script to parse distributed workload generation result 
# produced by fio in JSON format extracting total IOPS and avergae 95th percentile completion latencies
#
# assumption: fio command contains options:
#  --client C1 ... --client Cn --output-format=json --output=your-fio.out jobfile.fiojob
# usage: run this tool with
# ./fio-get-lat-iops.py your-fio.out
# 
# works only with fio v3.2 and later
# fio v3 outputs latencies in nanoseconds, not microseconds.

import os, sys
from pprint import pprint
import json

NOTOK=1
NSEC_PER_MSEC = 1000000

if len(sys.argv) < 2:
  print('usage: fio-json-prs.py fio-json.log')
  sys.exit(NOTOK)

# read the whole file
fn = sys.argv[1]
with open(fn, "r") as jsonf:
    records = jsonf.readlines()

# the first lines in the file contain a record for each host that participated in the test, 
# with prefix "hostname=", get the hostnames from these lines
k=0
hosts=[]
while k < len(records):
        r = records[k]
        k += 1
        if r.startswith('hostname='):
          h = r[9:].split(',')[0]
          hosts.append(h)

# the JSON output is preceded by a "Disk stats:" line, followed by "{" line.
found_json=-1
for k in range(0, len(records)):
        r = records[k]
#        if r.startswith('Disk stats'):
#        if r.startswith('Jobs: 0 (f=0)'):
#        if r.startswith('Jobs: '):
#          r2 = records[k+2]
#          r2 = records[k+1]
        if r == '{\n':
            found_json = k
            break

if found_json < 0:
        print("ERROR: could not find json string in fio output log %s to extract from"%fn)
        sys.exit(NOTOK)

# separate out pure JSON output into its own file
json_fn = fn + '.json'
with open(json_fn, 'w') as global_json:
        for k in range(found_json,len(records)):
                global_json.write(records[k])

# now that JSON data is isolated in a file, invoke JSON parser on it
# here we supply an example that extracts IOPS from the JSON file, but
# you can extract much, much more
read_per_host_iops = {}
write_per_host_iops = {}
read_per_host_clat = {}
write_per_host_clat = {}
read_total_iops = 0.0
write_total_iops = 0.0
read_total_clat = 0.0
write_total_clat = 0.0
with open(json_fn, 'r') as json_data:
        data = json.load(json_data)
        client_stats = data['client_stats']
        if ((len(hosts) > 1)  and (len(client_stats) != len(hosts) + 1) or
            (len(hosts) == 1) and (len(client_stats) != 1)):
            print('WARNING: client_stats field has %d entries, but there are %d hosts' 
                  % (len(client_stats), len(hosts)))
        if len(hosts) == 0:
            print('WARNING: no hosts found!')
            sys.exit(1)
        # extract whatever you want from JSON file by
        # using it as a python "dictionary" where you can lookup sub-fields by field name
        for client in client_stats:
          jobname = client['jobname']
          #print('%d, %s' % (c, jobname))
          if jobname == 'All clients':
            #print('skipping All clients aggregation')
            continue
          write_iops_num = client['write']['iops']
          write_clat_num = client['write']['clat_ns']['percentile']['95.000000'] / NSEC_PER_MSEC
          write_total_clat += write_clat_num
          read_iops_num = client['read']['iops']
          read_clat_num = client['read']['clat_ns']['percentile']['95.000000'] / NSEC_PER_MSEC
          read_total_clat += read_clat_num
          write_total_iops += client['write']['iops']
          read_total_iops += client['read']['iops']
        write_avg_clat = write_total_clat/len(client_stats)
        read_avg_clat = read_total_clat/len(client_stats)

# FIXME: maybe print out which is write and which is read
if write_total_iops > 0:
  #print '%s\t%s'%(write_total_iops,write_avg_clat)
  print 'write\t%s\t%.4f msec'%(write_total_iops,write_avg_clat)
  #print('total write IOPS: %s'%write_total_iops)
  #print('avg write CLAT: %s'%write_avg_clat)
if read_total_iops > 0:
  #print '%s\t%s'%(read_total_iops,read_avg_clat)
  print 'read\t%s\t%.4f msec'%(read_total_iops,read_avg_clat)
  #print('total read IOPS: %s'%read_total_iops)
  #print('avg read CLAT: %s'%read_avg_clat)
json_data.closed
os.remove(json_fn)
