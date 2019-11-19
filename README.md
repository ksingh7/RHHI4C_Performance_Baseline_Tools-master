## Red Hat Hyperconverged Infrastructure for Cloud (RHHI4C) Performance Baseline Tools
This repository contains tooling needed to perform initial performance benchmark for a OpenStack and Ceph cluster

## Prerequisite
- A running Openstack and Ceph environment with corretct networking setup and access controls.
- External network, router and dns server details
- Make sure Ceph is configured with best practices

## Initial setup

- Basic smoke test to verify OSP deployment

```
source overcloudrc
openstack compute service list
nova hypervisor-list
openstack host list
```
All the baseline testings must be carried using RHEL7 instances

- To download RHEL7 image file, use your Red Hat Customer Portal credentials and [visit](https://access.redhat.com/downloads/content/69/ver=/rhel---7/7.5/x86_64/product-software)
- Copy download URL for Red Hat Enterprise Linux KVM Guest Image
- On undercloud node (from where you are running the openstack commands) download the KVM image
```
cd /home/stack
wget https://access.cdn.redhat.com//content/origin/files/sha256/7f/7ff0d81ebf68119816b2756b7ed591dc9b50d29713e3785cc6bed564429a8b04/rhel-server-7.5-update-1-x86_64-kvm.qcow2?_auth_=1529563721_ec06a077c113db05ef691ce66b219af8 -O rhel-server-7.5-update-1-x86_64-kvm.qcow2
ls -l rhel-server-7.5-update-1-x86_64-kvm.qcow2
```
- Add the image to glance
```
cd /home/stack
qemu-img convert -f qcow2 -O raw rhel-server-7.5-update-1-x86_64-kvm.qcow2 rhel-server-7.5-update-1-x86_64-kvm.raw
openstack image create --public  --disk-format raw --file rhel-server-7.5-update-1-x86_64-kvm.raw rhel-server-7.5
openstack image list
```

## Heat Stack - 1 : Create External/Tenant netowrking, user, projecr, flavor & security group

Before you begin executing this stack, make sure provider network, tenant network, dns_nameservers details are correctly set in ``stack_1_network_flavor_sg_setup.yaml``

```
cd /home/stack
git clone https://github.com/red-hat-storage/RHHI4C_Performance_Baseline_Tools.git
cd /home/stack/RHHI4C_Performance_Baseline_Tools
openstack stack list
openstack stack create --wait --enable-rollback -t stack_1_network_flavor_sg_setup.yaml first_stack
```
- Once ``first_stack`` creation is successful, verify what's created

```
openstack flavor list
openstack network list
openstack router list
openstack security group list
```

## Admin Node Stack : Create admin-node instance, assign cinder volume and floating IP

```
openstack stack create --wait --enable-rollback -t stack_2_setup_admin_node.yaml admin_node_stack
```
- Once ``admin_node_stack`` creation is successful, verify what's created

```
openstack server list
openstack volume list
```
- Try SSH into admin-node (if networking setup is correct)
```
cd /home/stack
ssh -i stack.pem cloud-user@<Instance_Floating_IP>
```

At this point you have
- Running OSP and Ceph cluster 
- RHEL 7.5 glance image, keypair, security group created
- Provider, tenant OSP network setup
- Openstack project created
- 1 x Instances created with 1 x Cinder volume and 1 x Floating IP
- SSH to the instances working

## Setting up nodes for baseline testing

- Create server1 and verify by SSHing into it
```
cd /home/stack/RHHI4C_Performance_Baseline_Tools/baseline_env_setup
openstack stack create --wait --enable-rollback -t rhel_server1.yaml rhel_server1_stack
openstack stack list
```
```
openstack server list
cd /home/stack
ssh -i stack.pem cloud-user@<Floating IP of server2>
```
- Increase the quota in OpenStack to launch several instances

```
openstack quota show
openstack quota set admin --instances 20 --cores 80 --ram 102400 --volumes 20 --gigabytes 2000 
openstack quota show
```

- Once you have verified that server1 stack worked fine, launch the remaining stacks
```
for i in {2..10} ; do openstack stack create --wait --enable-rollback -t rhel_server$i.yaml rhel_server"$i"_stack ; done

openstack stack list
openstack server list
```

## Setting up Ansible on Undercloud Node

- Add server name and IP to /etc/hosts

```
openstack server list -c Name -c Networks -f value | awk '{ print $3 " "  $1}' | sudo tee -a /etc/hosts
```

- Setup ``/etc/ansible/hosts`` file

```
echo "[instances]" | sudo tee -a /etc/ansible/hosts
echo "server-[1:10]" | sudo tee -a /etc/ansible/hosts
echo "admin-node" | sudo tee -a /etc/ansible/hosts
```
- Test Ansible

```
ANSIBLE_HOST_KEY_CHECKING=False ansible instances -m ping -u cloud-user -b --private-key=/home/stack/stack.pem
```

## Initial instance configuration using Ansible

Before you run ansible-playbook, you must update 
- [group_vars/all.yaml](https://github.com/red-hat-storage/RHHI4C_Performance_Baseline_Tools/blob/master/ansiblezer/group_vars/all.yaml) with correct hostname in root public key
- Add server name and IP (private) to ``roles/common/templates/hosts``. This will be use to populate ``/etc/hosts`` file on all instances
```
openstack server list -c Name -c Networks -f value | cut  -d ' ' -f 1,2 | cut -d ',' -f 1 | sed  's/private_network1=//g' | awk '{print $2 , " " , $1}'| sudo tee -a /home/stack/RHHI4C_Performance_Baseline_Tools/ansiblezer/roles/common/templates/hosts
```
- Update ``templates/hosts.list`` file, this will be used by pdsh (pbench-fio)
```
openstack server list -c Name -f value | grep -v admin-node | sudo tee -a /home/stack/RHHI4C_Performance_Baseline_Tools/ansiblezer/roles/pbench/templates/hosts.list
```
- Test on admin-node first
```
ansible-playbook site.yaml -u cloud-user -b --private-key=/home/stack/stack.pem -t common,subscription,ssh,filesystem,pbench -l admin-node
```
- Run ansible on all remaining nodes
```
ansible-playbook site.yaml -u cloud-user -b --private-key=/home/stack/stack.pem -t common,subscription,ssh,filesystem,pbench -l 'instances:!admin-node' -f 10
```

## Setting up PBench and PBench-FIO

- on pbench-admin node create a ``hosts`` file under ``/root`` with all host names where you need to run benchmarking using PBench
- Setup PDSH on admin node

```
alias mypdsh="PDSH_SSH_ARGS_APPEND='-o StrictHostKeyChecking=no' PDSH_RCMD_TYPE=ssh pdsh -S -w ^hosts"
```
- Test PDSH , make sure you can reach all node passwordless

```
mypdsh 'hostname'
```
- Setup pbench-agent on admin node

```
. /etc/profile.d/pbench-agent.sh
cp /opt/pbench-agent/config/pbench-agent.cfg.example /opt/pbench-agent/config/pbench-agent.cfg
```
- Edit ``/opt/pbench-agent/config/pbench-agent.cfg ``

```
vi /opt/pbench-agent/config/pbench-agent.cfg 
```
  - uncomment RHEL has python-pandas
  
  ```
  pandas-package = python-pandas
  ```
  - Add the following to  ``/opt/pbench-agent/config/pbench-agent.cfg``
  ```
  [pbench-fio]
  version = 3.3
  histogram_interval_msec = 10000
  ```
- Configure ssh-key

```
configfile=/opt/pbench-agent/config/pbench-agent.cfg
keyfile=/root/.ssh/id_rsa
pbench-agent-config-activate $configfile
pbench-agent-config-ssh-key $configfile $keyfile
```
- Register pbench tools on pbench-admin node

```
pbench-list-tools
pbench-register-tool-set
```
- Register pbench tools on all other nodes

```
for host in $(cat hosts) ; do pbench-register-tool-set --remote=$host ; done
pbench-list-tools
```

- For OpenStack, it's a good idea to preallocate RBD images so that you get consistent performance results. To do this, you can dd to /dev/vdb like this (it could take a while):

```
mypdsh -f 15 'umount /var/lib/mysql'
mypdsh -f 15 'dd if=/dev/zero of=/dev/vdb bs=4096k conv=fsync'
mypdsh -f 15 'mkfs -t xfs /dev/vdb && mkdir -p /var/lib/mysql && mount -t xfs -o noatime /dev/vdb /var/lib/mysql'
```

- Make sure the disk you want to exercise is mounted
- Using default job file execute your first pbench-fio

```
/opt/pbench-agent/bench-scripts/pbench-fio  --samples=1 -t write -b 4 --client-file=hosts --targets=/mnt/rbd/file1

```
- Parase the PBench-fio results using a parser script written by my colleague [Ben England](https://github.com/bengland2). The python parser file is present in this repository, you need to move this parser file on to pbench-admin node.

```
python fio-get-lat-iops.ben3.py /var/lib/pbench-agent/fio*/1*/sample1/fio-result.txt
```
- The results should look like this

```
# python fio-get-lat-iops.ben3.py /var/lib/pbench-agent/fio*/1*/sample1/fio-result.txt
write	308445.522923	0.0000 msec
#
```
- Setup Drop Caches mechanism on all OSD hosts
  - Create drop caches script file ``/tmp/drop-caches.sh`` on all OSD nodes
```
cat > /tmp/drop-caches.sh << "EOF"
#!/bin/sh
sync
echo 3 > /proc/sys/vm/drop_caches
touch /tmp/drop_caches;date >> /tmp/drop_caches
EOF
```
  - Setup a cron job from root user on all OSD nodes
```
chmod +x /tmp/drop-caches.sh ; crontab -l > drop-caches ; echo "*/1 * * * * /tmp/drop-caches.sh" >> drop-caches ; crontab drop-caches; crontab -l ; rm -f drop-caches
```
- Setup Drop Caches mechanism on all VM Instances
  - Create a file ``/tmp/drop-caches.sh`` on pbench-admin node
```
cat > /tmp/drop-caches.sh << "EOF"
#!/bin/bash
pdsh -S -w ^/root/hosts 'sync ; echo 3 > /proc/sys/vm/drop_caches' ; touch /tmp/drop_caches;date >> /tmp/drop_caches
EOF
```
  - ``chmod +x /tmp/drop-caches.sh``
  
## Running your first PBench-FIO
- On Pbench-admin node create a PBench job file ``/root/fio-900-sec.job``

```
cat > /root/fio-900-sec.job << "EOF"
[global]
bs = $@
runtime = 900
ioengine = libaio
iodepth = 32
direct = 1
sync = 0
fsync = 1024
time_based = 1
clocksource = clock_gettime
ramp_time = 300
rwmixread = 75
rwmixwrite = 25
write_bw_log = fio
write_iops_log = fio
write_lat_log = fio
log_avg_msec = 1000
write_hist_log = fio
log_hist_msec = 10000

[job-$target]
filename = $target
rw = $@
size = 90000M
stonewall
numjobs = 1
EOF
```
- Execute this job from PBench admin node using the following command
```
time /opt/pbench-agent/bench-scripts/pbench-fio --pre-iteration-script=/tmp/drop-caches.sh --samples=1 --test-types=randwrite --block-sizes 4 --client-file=/root/hosts --job-mode=serial --targets=/mnt/rbd/file1 --job-file=/root/fio-900-sec.job
```
- Once PBench-fio is successful, it will create results in ``/var/lib/pbench-agent/fio__2018.06.29T10.59.54/1-randwrite-4KiB/sample1/fio-result.txt``
- Parse the results using ``fio-get-lat-iops.ben3.py`` script
```
# python fio-get-lat-iops.ben3.py  /var/lib/pbench-agent/fio__2018.06.29T10.59.54/1-randwrite-4KiB/sample1/fio-result.txt
write   12178.343682    88.7273 msec
#
```
- Perform cleanup

```
mypdsh 'rm -rf /mnt/rbd/file1'
```
## (optional) Set correct timezone on all nodes

```
timedatectl set-timezone Europe/Berlin ; 
mypdsh 'timedatectl set-timezone Europe/Berlin' ; 
mypdsh 'date' ; date
```

## Running a complex PBench-FIO test
Lets try to run a complex PBench-FIO test which includes the following excercise pattern
- Test Type : randwrite,randread,randrw
- Block Sizes : 4K,16K

We will use the same job file created in last section ``/root/fio-900-sec.job`` and just modify the PBench-FIO CLI

```
/opt/pbench-agent/bench-scripts/pbench-fio  --pre-iteration-script=/tmp/drop-caches.sh --samples=3 --test-types=randwrite,randread,randrw --block-sizes 4,16 --client-file=/root/hosts --job-mode=serial --targets=/mnt/rbd/file1 --job-file=/root/fio-900-sec.job
```
- Results for PBench-FIO complex run should look like below, notice the 6 result directories as wee needed

```
[root@admin-node fio__2018.06.29T19.01.46]# ls -l /var/lib/pbench-agent/fio__2018.06.29T19.01.46
total 162108
drwxr-xr-x. 5 root root       107 Jun 29 16:38 1-randwrite-4KiB
drwxr-xr-x. 5 root root       107 Jun 29 17:46 2-randwrite-16KiB
drwxr-xr-x. 5 root root       107 Jun 29 18:59 3-randread-4KiB
drwxr-xr-x. 5 root root       107 Jun 29 20:04 4-randread-16KiB
drwxr-xr-x. 5 root root       107 Jun 29 21:11 5-randrw-4KiB
drwxr-xr-x. 5 root root       107 Jun 29 22:17 6-randrw-16KiB
-rw-r--r--. 1 root root        91 Jun 29 22:17 fio-client.file
-rwxr-xr-x. 1 root root       343 Jun 29 22:17 generate-benchmark-summary.cmd
-rw-r--r--. 1 root root      4200 Jun 29 22:28 metadata.log
-rw-r--r--. 1 root root      5259 Jun 29 22:28 result.csv
-rw-r--r--. 1 root root     61277 Jun 29 22:28 result.html
-rw-r--r--. 1 root root 165890661 Jun 29 22:28 result.json
-rw-r--r--. 1 root root     19394 Jun 29 22:28 result.txt
drwxr-xr-x. 4 root root        28 Jun 29 22:28 sysinfo
drwxr-xr-x. 2 root root         6 Jun 29 15:02 tmp
[root@admin-node fio__2018.06.29T19.01.46]#
```

- Let's parse these results using the below one liner

```
for i in {1..6} ; do for j in 1 2 3 ; do python fio-get-lat-iops.ben3.py /var/lib/pbench-agent/fio__2018.06.29T19.01.46/$i-*/sample$j/fio-result.txt | grep -vi warning  ; done ; done
```

- Parsed results shoudl look like this

```
[root@admin-node ~]# for i in {1..6} ; do for j in 1 2 3 ; do python fio-get-lat-iops.ben3.py /var/lib/pbench-agent/fio__2018.06.29T19.01.46/$i-*/sample$j/fio-result.txt | grep -vi warning  ; done ; done
write   13996.403744    78.6364 msec
write   11661.001586    4.9091 msec
write   12415.237432    3.7273 msec
write   5303.55347      687.0000 msec
write   2853.076338     755.8182 msec
write   3176.688836     534.9091 msec
read    9584.45953      93.3636 msec
read    10738.64525     83.0000 msec
read    11162.29753     88.0000 msec
read    6675.28246      92.6364 msec
read    5784.45473      92.4545 msec
read    6620.94385      101.5455 msec
write   1845.528222     0.0000 msec
read    1612.90323      122.0909 msec
write   7286.438498     0.0000 msec
read    125000.0        122.3636 msec
write   7347.449651     0.0000 msec
read    125000.0        118.2727 msec
write   855.516346      194.0000 msec
read    944.88189       280.8182 msec
write   10913.980316    138.1818 msec
read    240000.0        265.0909 msec
write   10930.644649    119.0000 msec
read    240000.0        268.7273 msec
[root@admin-node ~]#

```
- Let's understand the output, in the complex PBench test we ran 3 samples of each 4K and 6K of type RandWrite, RandRead, RandReadWrite.
- The first 3 rows from the output are sample 1,2,3 of 4K, RandWrite
- The second 3 rows from the output are samples 1,2,3 of 16K, RandWrite
- The thrid 3 rows from the output are samples 1,2,3 of 4K, RandRead

It goes in the same order, just plot them in a excel as you like and.

## Setting up MySQL database on OpenStack Instances

- Before we start setting up MySQL databases, lets firs delete the data from cinder volumes that we have generated with PBench-FIO. Login to PBench-admin node and delete ``file1``and unmount volume.

```
mypdsh 'rm -f /mnt/rbd/file1'
mypdsh 'umount /mnt/rbd'
```
- Lets run ansible to install and configure MySQL on all 10 instnaces. Login to undercloud node and run ansible with correct tags.

```
ansible-playbook site.yaml -u cloud-user -b --private-key=/home/stack/stack.pem -t filesystem,mysql -f 10
```

- To verify MySQL database installation from PBench-admin node 

```
mypdsh ' ps -ef | grep -i mysqld'
```
- Verify that MySQL database is using Cinder volume

```
mypdsh 'df -h /var/lib/mysql'
```
## Excercising MySQL DB running on Ceph
Run the following commands from PBench-admin node
- Install Sysbench and mariadb client
```
yum install -y sysbench mariadb --disablerepo=ndokos-pbench
```
- Disable firewall on all instances
```
mypdsh 'systemctl stop firewalld'
```

- Create a scrip file and transer it to all instances
```
cat > /tmp/mysql.sh << "EOF"
#!/bin/bash
mysql -u root -e "CREATE DATABASE sysbench;"
mysql -u root -e "CREATE USER 'sysbench'@'%' IDENTIFIED BY 'secret';"
mysql -u root -e "GRANT ALL PRIVILEGES ON *.* TO 'sysbench'@'%' IDENTIFIED  BY 'secret';"
EOF
```
```
for i in {1..10} ; do scp /tmp/mysql.sh server-$i:/tmp/mysql.sh ; done
mypdsh 'chmod +x /tmp/mysql.sh'
```
- Execute the script file to create database and user on all instances
```
mypdsh 'sh /tmp/mysql.sh'
```
- Verity that user and database is successfully created on all instances
```
for i in {1..10} ; do mysql -h server-$i -u sysbench -psecret -e 'SHOW DATABASES' ; done
```

- Generate some test data into every MySQL instances 
```
for i in {1..10} ; do sysbench oltp_write_only --threads=128 --table_size=50000000 --mysql-host=server-$i --mysql-db=sysbench --mysql-user=sysbench --mysql-password=secret --db-driver=mysql --mysql_storage_engine=innodb prepare &  done
```
- Verify that dataset has been generated into the database

```
for i in {1..10} ; do mysql -h server-$i -u sysbench -psecret -e 'SELECT TABLE_NAME, TABLE_ROWS FROM information_schema.tables WHERE `table_schema` = "sysbench" ;' ; done
```
- Drop caches on all OSD and OpenStack Instances (follow the method explained previously)

### MySQL Write Test

- Performa a Write test on all databases

```
RUN=1 ; for i in {1..10} ; do FILE=/tmp/server-"$i"_write_test_"$RUN".log ; touch $FILE ; > $FILE ; sysbench oltp_write_only --table_size=50000000  --mysql-host=server-$i --mysql-db=sysbench --mysql-user=sysbench --mysql-password=secret --db-driver=mysql --mysql_storage_engine=innodb --percentile=99 --time=900 --threads=16  run  > $FILE & done ; ps -ef | grep -i sysbench
```

- Once test is completed use the following one-liner to extract the results

##### Transactions
```
RUN=1 ; for i in {1..10} ; do FILE=/tmp/server-"$i"_write_test_"$RUN".log ; cat $FILE | egrep -i "transactions:|queries:|percentile:" | awk '{print $1,$2,$3}' | cut -d '(' -f 1 ; done | grep -i "transactions:" | cut -d ' ' -f 2
```

##### Queries
```
RUN=1 ; for i in {1..10} ; do FILE=/tmp/server-"$i"_write_test_"$RUN".log ; cat $FILE | egrep -i "transactions:|queries:|percentile:" | awk '{print $1,$2,$3}' | cut -d '(' -f 1 ; done | grep -i "queries:" | cut -d ' ' -f 2
```

##### 99th Percentile Latency
```
RUN=1 ; for i in {1..10} ; do FILE=/tmp/server-"$i"_write_test_"$RUN".log ; cat $FILE | egrep -i "transactions:|queries:|percentile:" | awk '{print $1,$2,$3}' | cut -d '(' -f 1 ; done | grep -i "percentile:" | cut -d ' ' -f 3
```

##### Avg Latency

```
RUN=1 ; for i in {1..10} ; do FILE=/tmp/server-"$i"_write_test_"$RUN".log ; cat $FILE | egrep -i "transactions:|queries:|percentile:|avg:" | awk '{print $1,$2,$3}' | cut -d '(' -f 1 ; done | grep -i "avg:" | cut -d ' ' -f 2
```

### MySQL Read Test

- Performa a Read test on all databases

```
RUN=1 ; for i in {1..10} ; do FILE=/tmp/server-"$i"_read_test_"$RUN".log ; touch $FILE ; > $FILE ; sysbench oltp_read_only --table_size=50000000  --mysql-host=server-$i --mysql-db=sysbench --mysql-user=sysbench --mysql-password=secret --db-driver=mysql --mysql_storage_engine=innodb --percentile=99 --time=900 --threads=16  run  > $FILE & done ; ps -ef | grep -i sysbench
```

- Once test is completed use the following one-liner to extract the results

##### Transactions
```
RUN=1 ; for i in {1..10} ; do FILE=/tmp/server-"$i"_read_test_"$RUN".log ; cat $FILE | egrep -i "transactions:|queries:|percentile:" | awk '{print $1,$2,$3}' | cut -d '(' -f 1 ; done | grep -i "transactions:" | cut -d ' ' -f 2
```

##### Queries
```
RUN=1 ; for i in {1..10} ; do FILE=/tmp/server-"$i"_read_test_"$RUN".log ; cat $FILE | egrep -i "transactions:|queries:|percentile:" | awk '{print $1,$2,$3}' | cut -d '(' -f 1 ; done | grep -i "queries:" | cut -d ' ' -f 2
```
##### 99th Percentile Latency
```
RUN=1 ; for i in {1..10} ; do FILE=/tmp/server-"$i"_read_test_"$RUN".log ; cat $FILE | egrep -i "transactions:|queries:|percentile:" | awk '{print $1,$2,$3}' | cut -d '(' -f 1 ; done | grep -i "percentile:" | cut -d ' ' -f 3
```

##### Avg Latency
```
RUN=1 ; for i in {2..11} ; do FILE=/tmp/server-"$i"_read_test_"$RUN".log ; cat $FILE | egrep -i "transactions:|queries:|percentile:|avg:" | awk '{print $1,$2,$3}' | cut -d '(' -f 1 ; done | grep -i "avg:" | cut -d ' ' -f 2
```

### MySQL Read/Write Mix Test

- Perform Read/Write Mix test on all databases

```
RUN=2 ; for i in {1..10} ; do FILE=/tmp/server-"$i"_read_write_test_"$RUN".log ; touch $FILE ; > $FILE ; sysbench oltp_read_write --table_size=50000000  --mysql-host=server-$i --mysql-db=sysbench --mysql-user=sysbench --mysql-password=secret --db-driver=mysql --mysql_storage_engine=innodb --percentile=99 --time=900 --threads=16  run  > $FILE & done ; ps -ef | grep -i sysbench
```

- Once test is completed use the following one-liner to extract the results

##### Transactions

```
RUN=2 ; for i in {1..10} ; do FILE=server-"$i"_read_write_test_"$RUN".log ; cat $FILE | egrep -i "transactions:|queries:|percentile:" | awk '{print $1,$2,$3}' | cut -d '(' -f 1 ; done | grep -i "transactions:" | cut -d ' ' -f 2
```

##### Queries

```
RUN=2 ; for i in {1..10} ; do FILE=server-"$i"_read_write_test_"$RUN".log ; cat $FILE | egrep -i "transactions:|queries:|percentile:" | awk '{print $1,$2,$3}' | cut -d '(' -f 1 ; done | grep -i "queries:" | cut -d ' ' -f 2
```

##### 99th Percentile Latency
```
RUN=2 ; for i in {1..10} ; do FILE=server-"$i"_read_write_test_"$RUN".log ; cat $FILE | egrep -i "transactions:|queries:|percentile:" | awk '{print $1,$2,$3}' | cut -d '(' -f 1 ; done | grep -i "percentile:" | cut -d ' ' -f 3
```

##### Avg Latency
```
RUN=2 ; for i in {1..10} ; do FILE=server-"$i"_read_test_"$RUN".log ; cat $FILE | egrep -i "transactions:|queries:|percentile:|avg:" | awk '{print $1,$2,$3}' | cut -d '(' -f 1 ; done | grep -i "avg:" | cut -d ' ' -f 2

```

## Troubleshooting

- PBench
  - On pbench-admin node make sure to have enough RAM else you might get errors like "Out of Memory"




