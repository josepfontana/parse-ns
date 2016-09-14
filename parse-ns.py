#!/usr/bin/python2.7

################################################################################
#
# parse-ns.py
# 
# v1.0 15/09/2016 - Josep Fontana - Initial version
#
# Parse running/saved configuration of Citrix Netscaler in the provided files
# and output 2 csv files:
# one for load balancing with the backend IP(s) and their correspondence with frontend IP
# a second one for global server load balance with the domains and their corresponding IP(s)
#


"""
 Handy definitions from:
  http://support.citrix.com/article/CTX120318
  https://www.syxin.com/2014/03/netscaler-nsipsnipmipvip/

 NIP: Netscaler IP (management interface, also NSIP)
 VIP: Virtual IP (used for client-side connections)
 SNIP: SubNet IP (used for server-side connections)
 MIP: Mapped IP (default SNIP)


                          +-----------+            +-----------+
  +----------+            |           |            |           |
  |          |        VIP |           |SNIP      IP|   Front   |
  |  Client  +<---------->+ Netscaler +<---------->+           |
  |          |            |           |            | Server(s) |
  +----------+            |           |            |           |
                          +-----------+            +-----------+


 This is the path we will take from the IP to the VIP
  1. ip->name (add server)
     add server [serverName] [IP] -comment ["some code or explanation"]
  2. name->serviceGroup (bind serviceGroup)
     bind serviceGroup [serviceGroup] [serverName] [port] -CustomServerID ["some code"]
  3. serviceGroup->vserver (bind lb vserver)
     bind lb vserver [vserver] [serviceGroup]
  4. vserver->vip (add lb vserver)
     add lb vserver [vserver] [serviceType] [VIP] [port] -comment ["some code"] [other parameters]


And then we have GSLB (Global Server Load Balancing). A lot of information can be found on https://support.citrix.com/servlet/KbServlet/download/22506-102-671576/gslb-primer_FINAL_1019.pdf
Here we go from the server to the domainName that the Netscaler will solve:
  1. ip->name (add server) same as above
     add server [serverName] [IP] -comment ["some code or explanation"]
  2. name->service (add gslb service)
     add gslb service [gslbservice] [serverName] [serviceType] [port] [other parameters] -comment ["some code or explanation"]
  3. service->vserver (bind gslb vserver)
     bind gslb vserver [vserver] -serviceName [gslbservice]
  4. vserver->domainName
     bind gslb vserver [vserver] -domainName [domainName] [other parameters]
"""


################################################################################
# init and argument parsing
################################################################################


#####
# imports

import sys
import os
import csv
import datetime


#####
# dictionaries

# common
servers=dict()		# [srvName, srvComment]=servers[ip]
srvs=dict()	        # [serviceGroup/gslbService, 'LB'/serviceType, port, srvComment]=srvs[srvName]
vServers=dict()		# vServer=vServers[serviceGroup/gslbService]
# lb
VIPs=dict()		# [VIP, serviceType, port, VIPcomment]=VIPs[vServer]
# gslb
domains=dict()         # domain=domains[vserver]


#####
# argument parsing

confFiles=sys.argv
del confFiles[0]
if (confFiles==[]):
    # no parameter where given
    print "\n *** ERROR: no configuration files were provided in the command line\n"
    print "Please use the following syntax:"
    print " parse-ns.py conf1.txt conf2.txt ...\n"
    exit(1)


################################################################################
# parsing functions
################################################################################

"""
readline(line)
 read line and parse accordingly
"""
def readline(line):
    # the first one is for lb and gslb
    if (line.lower().startswith('add server')):
        server_parse(line)
    # the three next are for lb
    elif (line.lower().startswith('bind servicegroup')): 
        bind_servicegroup_parse(line)

    elif (line.lower().startswith('bind lb vserver')):
        bind_lb_parse(line)

    elif (line.lower().startswith('add lb vserver')):
        lb_vserver_parse(line)
    # here we start with gslb-specific stuff
    elif (line.lower().startswith('add gslb service')):
        gslb_parse(line)
    elif (line.lower().startswith('bind gslb vserver')):
        gslb_vserver_parse(line)


"""
add server [serverName] [IP] -comment ["some code or explanation"]
"""
def server_parse(l):
    srvName=l.split()[2]
    IP=l.split()[3]
    srvComment=line.partition('-comment ')[2].strip('"\n')
    
    servers[IP]=[srvName, srvComment]
    

"""
bind serviceGroup [serviceGroup] [serverName] [port] -CustomServerID ["some code"]
these lines are sometimes followed by:
    bind serviceGroup [serviceGroup] -monitorName [monitor]
which may delete the data we want to get from the dictionary!
"""
def bind_servicegroup_parse(l):
    if '-monitorName' in l:
        # nothing to do here
        return
    
    serviceGroup=l.split()[2]
    srvName=l.split()[3]
    port=l.split()[4]
    srvComment=l.partition('-CustomServerID ')[2].strip('"\n')

    srvs[srvName]=[serviceGroup, 'LB', port, srvComment]

"""
bind lb vserver [vserver] [serviceGroup]
"""
def bind_lb_parse(l):
    vServer=l.split()[3]
    serviceGroup=l.split()[4]

    vServers[serviceGroup]=vServer

"""
add lb vserver [vserver] [serviceType] [VIP] [port] [-other parameters] -comment ["some code"]
"""
def lb_vserver_parse(l):
    vServer=l.split()[3]
    serviceType=l.split()[4]
    VIP=l.split()[5]
    port=l.split()[6]
    VIPcomment=l.partition('-comment ')[2].strip('"\n')

    VIPs[vServer]=[VIP, serviceType, port, VIPcomment]

"""
add gslb service [gslbservice] [serverName] [serviceType] [port] [other parameters] -comment ["some code or explanation"]
"""
def gslb_parse(l):
    gslbService=l.split()[3]
    srvName=l.split()[4]
    serviceType=l.split()[5]
    port=l.split()[6]
    srvComment=l.partition('-comment ')[2].strip('"\n')

    srvs[srvName]=[gslbService, serviceType, port, srvComment]


"""
bind gslb vserver [vserver] -serviceName [gslbservice]
bind gslb vserver [vserver] -domainName [domainName] [other parameters]
"""
def gslb_vserver_parse(l):
    if '-serviceName' in l:
        vServer=l.split()[3]
        gslbService=l.split()[5]

        vServers[gslbService]=vServer
    elif '-domainName' in l:
        vserver=l.split()[3]
        domain=l.split()[5]

        # if there's already a domain for this vserver just add it
        try:
            domains[vserver]=domains[vserver]+'\n'+domain
        except KeyError:
            domains[vserver]=domain



################################################################################
# information input
################################################################################

# go through each file provided in the command line
for confFile in confFiles:
    print "Reading "+confFile+"..."
    # open file and read it line by line
    with open(confFile,'r') as f:
        for line in f:
            readline(line)


################################################################################
# information output
################################################################################

# create the filenames from the date/time
d=datetime.datetime
# nasty one-liner to get a 'YYY-MM-DD_HH.MM' string
#f_basename=d.now().isoformat('_').partition('.')[0].replace(':','.').rstrip('1234567890').rstrip('.')
# ok, ok, it's better to use strftime!
f_basename=d.now().strftime('%Y-%m-%d_%H.%M')

f_lb=f_basename+'_LB.csv'
f_gslb=f_basename+'_GSLB.csv'


with open(f_lb,'w') as f:
    print "Writing "+f_lb+"..."
    # create the csv writer
    w=csv.writer(f)

    # write the header row
    w.writerow( ('VIP', 'serviceType', 'port', 'VIPcomment', 'vServer', 'serviceGroup', 'port', 'CustomServerID', 'srvName', 'srvComment', 'IP') )

    # loop through the servers and get those that are LB'ed
    for IP in servers.keys():
        [srvName, srvComment]=servers[IP]
        try:
            [serviceGroup, notUsed, port, CustomServerID]=srvs[srvName]
        except(KeyError):
            continue
        try:
            vServer=vServers[serviceGroup]
        except(KeyError):
            continue
        try:
            [VIP, serviceType, VIPport, VIPcomment]=VIPs[vServer]
        except(KeyError):
            continue

        w.writerow( (VIP, serviceType, VIPport, VIPcomment, vServer, serviceGroup, port, CustomServerID, srvName, srvComment, IP) )


with open(f_gslb,'w') as f:
    print "Writing "+f_gslb+"..."
    # create the csv writer
    w=csv.writer(f)

    # write the header row
    w.writerow( ('domain', 'vServer', 'gslbService', 'serviceType', 'port', 'srvcComment', 'srvComment', 'srvName', 'IP') )

    # loop through the servers and get those that are GSLB'ed
    for IP in servers.keys():
        [srvName, srvComment]=servers[IP]
        try:
            [gslbService, serviceType, port, srvcComment]=srvs[srvName]
        except(KeyError):
            continue
        try:
            vServer=vServers[gslbService]
        except(KeyError):
            continue
        try:
            domain=domains[vServer]
        except(KeyError):
            continue

        w.writerow( (domain, vServer, gslbService, serviceType, port, srvcComment, srvComment, srvName, IP) )

print "...and done! Enjoy!"
