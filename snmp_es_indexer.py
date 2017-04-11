import argparse, json, os, sys, time
import datetime
import yaml
import logging.config
from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk

from snmp_processor import SNMPManager, process_job

parser = argparse.ArgumentParser()
parser.add_argument("--snmp_host", default="localhost:161", help="Agent to retrieve variables from")
parser.add_argument("--community", default="public", help="Community string to query the agent")
parser.add_argument("--version", type=int, default=2, help="SNMP Version")
parser.add_argument("--es_host", default="localhost:9200", help="ES Connection String")
parser.add_argument("--es_user", default="elastic", help="ES User")
parser.add_argument("--use_ssl", help="Use SSL for ES",action='store_true', dest="use_ssl", default=False)
parser.add_argument("--es_password", default="changeme", help="ES Password")
parser.add_argument("--job_file", default="job_file.json", help="Job File for SNMP Poller")
parser.add_argument("--poll_rate", default=30, type=int, help="Poll Rate in seconds")
parser.add_argument("--es_template", default="./snmp_template.json", help="ES Template")
parser.add_argument("--log_conf", default="logging.conf", help="Log Conf File")
parser.add_argument("--pipeline", default=None, help="Ingest Pipeline - Name Only")


options = parser.parse_args()
# create happy_logger
log_config = yaml.safe_load(open(options.log_conf,'r'))
logging.config.dictConfig(log_config)
snmp_logger = logging.getLogger('snmp')

client = Elasticsearch(hosts=[options.es_host], http_auth = (options.es_user, options.es_password), use_ssl = options.use_ssl, verify_certs=True)
try:
    cluster = client.info()
except:
    snmp_logger.error('Unable to contact ES cluster. Exiting.', exc_info=True)
    sys.exit(1)


snmp_logger.info("Inserting snmp template from %s"%options.es_template)
with open(options.es_template, 'r') as json_template:
    client.indices.put_template(name="snmp", body=json.loads(json_template.read()))
    snmp_logger.info("snmp template inserted")

snmp_manager = SNMPManager(options.snmp_host,options.community,options.version)
is_alive = snmp_manager.is_alive()
if not is_alive:
    snmp_logger.error("Exiting as SNMP Host is not reachable")
    sys.exit(1)


def process_jobs(snmp_manager,job_filename,pipeline):
    if os.path.isfile(job_filename):
        snmp_logger.info("Processing job file %s" % job_filename)
        with open(job_filename) as job_file:
            jobs = json.loads(job_file.read())
            for job in jobs:
                cnt = 0
                try:
                    for _ in streaming_bulk(
                            client,
                            process_job(snmp_manager, job),
                            chunk_size=100,
                            index='snmp-%s' % timestamp[:10],
                            pipeline=pipeline
                    ):
                        cnt += 1
                        if cnt % 1000 == 0:
                            snmp_logger.info('%s docs indexed' % cnt)
                except:
                    snmp_logger.error(
                        "An exception occurred during document indexing, %s docs indexed. Possibly incomplete." % cnt,
                        exc_info=True)
    else:
        snmp_logger.info("No job file found at %s"%job_filename)



while True:
    current_time = time.time()
    snmp_logger.info("Processing jobs...")
    timestamp = datetime.datetime.utcnow().isoformat()[:-7]+'Z'
    process_jobs(snmp_manager,options.job_file,options.pipeline)
    time_spent = time.time() - current_time
    #if polling within time i.e. no delays, aim to meet regular poll_time. If < 0 there has been polls and just poll immediately
    if (options.poll_rate - time_spent) > 0:
        wait_time = options.poll_rate - time_spent
        snmp_logger.info("Sleeping %s seconds before next poll" % str(wait_time))
        time.sleep(wait_time)
    else:
        snmp_logger.info("Poll period exceeded. Polling immediately.")





