import argparse, json, os, sys, time
import csv
import datetime

from snmp_processor import SNMPManager, snmp_logger, process_job

parser = argparse.ArgumentParser()
parser.add_argument("--snmp_host", default="localhost:161", help="Agent to retrieve variables from")
parser.add_argument("--community", default="public", help="Community string to query the agent")
parser.add_argument("--version", type=int, default=2, help="SNMP Version")
parser.add_argument("--output_file", default="ip_mac.csv", help="Client IP to AP mapping")
parser.add_argument("--poll_rate", default=10, type=int, help="Poll Rate in seconds")
options = parser.parse_args()

job = {
    "job_name":"AP Stations",
    "key_field":"RUCKUS-ZD-WLAN-MIB::ruckusZDWLANStaMacAddr",
    "key_type":"mac_address",
    "type":"ap_connection",
    "fields": {
      "RUCKUS-ZD-WLAN-MIB::ruckusZDWLANStaAPMacAddr":{
        "field_name":"access_point_mac"
      },
      "RUCKUS-ZD-WLAN-MIB::ruckusZDWLANStaIPAddr":{
        "field_name":"client_ip"
      }
    }
}

snmp_manager = SNMPManager(options.snmp_host,options.community,options.version)
is_alive = snmp_manager.is_alive()
if not is_alive:
    snmp_logger.error("Exiting as SNMP Host is not reachable")
    sys.exit(1)

while True:
    current_time = time.time()
    snmp_logger.info("Obtaining AP Macs for current Client IPs")
    timestamp = datetime.datetime.utcnow().isoformat()[:-7]+'Z'
    #rewrite the whole file
    with open(options.output_file,'w') as output_file:
        product_writer = csv.writer(output_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
        for doc in process_job(snmp_manager, job):
            product_writer.writerow([doc['client_ip'],doc['access_point_mac']])
    time_spent = time.time() - current_time
    #if polling within time i.e. no delays, aim to meet regular poll_time. If < 0 there has been polls and just poll immediately
    if (options.poll_rate - time_spent) > 0:
        wait_time = options.poll_rate - time_spent
        snmp_logger.info("Sleeping %s seconds before next poll" % str(round(wait_time,2)))
        time.sleep(wait_time)
    else:
        snmp_logger.info("Poll period exceeded. Polling immediately.")