import  sys, time
import datetime
import yaml
import logging.config
from easysnmp import EasySNMPTimeoutError
from easysnmp import Session
import hashlib

log_config = yaml.safe_load(open('logging.conf','r'))
logging.config.dictConfig(log_config)
snmp_logger = logging.getLogger('snmp')

value_cache = {
}

class JobValueError(ValueError):
    '''raise this when there's a parameter parsing error'''

class SNMPManager():
    _session_ = None
    _snmp_host_ = None

    def __init__(self,snmp_host,community,version):
        self._snmp_host_ = snmp_host
        self._session_ = Session(hostname=snmp_host, community=community, version=version, use_long_names=True, use_sprint_value=True)

    def is_alive(self):
        try:
            val = self._session_.get('SNMPv2-MIB::sysName.0')
            if val.value:
                return True
        except:
            snmp_logger.error("Unable to reach snmp host %s"%self._snmp_host_, exc_info=True)
            pass
        return False

    def walk_oid(self,oid_name):
        try:
            return self._session_.walk(oid_name)
        except EasySNMPTimeoutError as timeout:
            snmp_logger.error("SNMP Timeout Error,",exc_info=True)
            snmp_logger.info("No values will be collected")
            return []

def _mac_to_decimal(mac):
    octets = mac.split(':')
    vals = []
    for octet in octets:
        vals.append(str(int(octet, 16)))
    return '.'.join(vals)

def _decimal_to_mac(mac):
    vals = mac.split('.')
    hex_vals = []
    for val in vals:
        hex_vals.append(hex(int(val))[2:])
    return ':'.join(hex_vals)

def _obfuscate_mac_address(mac_address):
    #obfuscate for display only
    return hashlib.md5(str.encode(mac_address)).hexdigest()

#Currently we assume the value can't wrap - Counter64 for example
def _get_oid_delta(key,oid, value):
    current_time = time.time()
    if key in value_cache:
        if oid in value_cache[key]:
            t_delta = current_time - value_cache[key][oid][0]
            v_delta = float(value) - value_cache[key][oid][1]
            delta = int(v_delta/t_delta)
            value_cache[key][oid] = (current_time, float(value))
            return delta
        else:
            value_cache[key][oid] = (current_time, float(value))
    else:
        value_cache[key] = { oid: (current_time, float(value)) }
    return None

def _add_mac_indexed_stat(snmp_manager,aps, oid_name, field_config):
    values = snmp_manager.walk_oid(oid_name)
    for value in values:
        key = _decimal_to_mac('.'.join(value.oid_index.split('.')[-6:]))
        obfuscate =  True  if 'obfuscate' in field_config and field_config['obfuscate'] else False
        rate_field = field_config['rate_field'] if 'rate_field' in field_config else None
        if obfuscate and rate_field:
            snmp_logger.error('Incompatible config values for field - obfuscate and rate_field are not compatible')
            sys.exit(1)
        indexed_value = _obfuscate_mac_address(value.value) if obfuscate  else value.value
        if key in aps:
            aps[key][field_config['field_name']] = indexed_value
        else:
            aps[key] = {}
            aps[key][field_config['field_name']] = indexed_value
        delta_value = _get_oid_delta(key, oid_name, indexed_value) if rate_field else None
        if delta_value is not None:
            aps[key][field_config['rate_field']] = delta_value

def _collect_docs_for_oid_table(snmp_manager,key_oid, oids={}, obfuscate_key=False):
    docs = {}
    mac_addresses = snmp_manager.walk_oid(key_oid)
    if len(mac_addresses) > 0:
        for mac_address in mac_addresses:
            mac = mac_address.value
            docs[mac_address.value] = {'mac_address':_obfuscate_mac_address(mac) if obfuscate_key else mac,'@timestamp':datetime.datetime.utcnow().isoformat()[:-7]+'Z'}
        for oid, mapping in oids.items():
            _add_mac_indexed_stat(snmp_manager,docs, oid, mapping)
    return docs

def _get_job_field(job, field, default=None):
    if field in job:
        return job[field]
    elif default is None:
        raise JobValueError("Missing required job parameter: %s"%field)
    else:
        return default

def _collect_docs_for_type(snmp_manager, type, key_field, fields, **kwargs):
    for _key,doc in _collect_docs_for_oid_table(snmp_manager,key_field, fields, **kwargs).items():
        doc["_type"] = type
        yield doc

def process_job(snmp_manager,job):
    try:
        job_name = _get_job_field(job, 'job_name')
        snmp_logger.info("Processing job %s" % job_name)
        type = _get_job_field(job, 'type', default='snmp')
        key_field = _get_job_field(job, 'key_field')
        obfuscate_key = _get_job_field(job, 'obfuscate_key', default=False)
        fields = _get_job_field(job, 'fields', default=[])
        yield from _collect_docs_for_type(snmp_manager, type, key_field, fields, obfuscate_key=obfuscate_key)
        snmp_logger.info("Job %s complete"%job_name)
    except JobValueError as e:
        snmp_logger.error("Skipping job as required field missing",exc_info=True)
        return



