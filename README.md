# Ruckus SNMP Poller

Python code used to collect SNMP statistics from Ruckus ZD 3000.  This code was used for data collection for the Operational Analytics Demo at Elastic{ON} 2017 as described [here](https://elastic.co/blog/operational-analytics-at-elasticon-2017-part-1).

This code **may** work with other SNMP devices.  An attempt was made to ensure the polling code was generic to allow for device changes at the event.  How this has not been tested. **This code is provided in good faith only and is not supported.**

# Requirements

1. Python 3.4.
1. See [`requirements.txt`] (https://github.com/gingerwizard/ruckus-snmp-poller/requirements.txt) for python library dependencies.
1. **NET-SNMP version 5.7.3**.  The python easysnmp will not work without it.
1. python build packages - `sudo apt-get install libpq-dev python3-dev libxml2-dev libxslt1-dev libldap2-dev libsasl2-dev libffi-dev`
1. The MIB files for the device being polled must be copied to the the directory `$HOME/.snmp/mibs` or `/usr/local/share/snmp/mibs` for the user under which the script will run.  [MIB files](https://github.com/gingerwizard/ruckus-snmp-poller/ZD_MIBS) for a Ruckas Zone Director are provided, which support the default configuration.


## OSX Note for NET-SNMP:

On osx you will need install easy_snmp from source with the following flags - as 5.6 is install by default (this can't be easily replaced): 

* LDFLAGS:  -L/usr/local/opt/net-snmp/lib
* CPPFLAGS: -I/usr/local/opt/net-snmp/include


## Scripts

3 scripts are provided:

1. `snmp_processor.py` - Provides the core functions for SNMP Polling. The method process_job is used by subsequent scripts. This method should be passed an SNMP_Manager and job instance. Yields documents an iterator.
2. `snmp_es_indexer.py` - Uses the snmp_processor.py script to poll the SNMP doc and index into Elasticsearch.  The script reads the configured job file through the parameter --job_file (defaults to job_file.json). Each object in the list represents a type of document to index, describing the specification of oid values to field names e.g.

    `{
        "job_name":"AP Stations",
        "key_field":"RUCKUS-ZD-WLAN-MIB::ruckusZDWLANStaMacAddr",
        "key_type":"mac_address",
        "type":"ap_connection",
        "obfuscate_key":true,
        "fields": {
          "RUCKUS-ZD-WLAN-MIB::ruckusZDWLANStaAPMacAddr":{
            "field_name":"access_point_mac"
          },
          "RUCKUS-ZD-WLAN-MIB::ruckusZDWLANStaUser":{
            "field_name":"logged_in_user"
          },
          "RUCKUS-ZD-WLAN-MIB::ruckusZDWLANStaIPAddr":{
            "field_name":"client_ip"
          },
          "RUCKUS-ZD-WLAN-MIB::ruckusZDWLANStaAvgRSSI":{
            "field_name":"avg_rssi"
          }
        }
    }`

    Each job contains the following keys:
    
        * `job_name` - Name of job. For logging purposes only. **Required**
        * `key_field` - When creating a document for this specification this oid is used as the key for a document.  All unique values, identified in an snmp_walk, of this oid will be used to create a document instance.  Typically this is a mac address and is used to identify the associated oids values, listed under fields, for each document. **Required**
        * `key_type` - specifies the type of the `key_field`. Currently only 'mac_address' is supported.
        * `type` - document type into which the documents will be indexed. **Required**
        * `fields` - OID to field value mapping. Each oid value is retrieved and added to the appropriate document instance under the field name. This is achieved using an snmp_walk.  The oid value to associate for each document is based on the `key_field` value - currently a mac address. **Required**
        * `obfuscate_key` - added for the purpose of the demo. Hashes the key field.
    
    The script in turn polls the configured snmp device, configured through the parameter `snmp_host` (defaults to localhost:161), for each document type indexing the resultant docs into a daily index with the prefix snmp-<datestamp>.  This poll occurs every N seconds - configurable through the parameter `poll_rate` (default 30 seconds).  Documents are timestamped based on the poll time.
    
    This accepts the following parameters:

        * `snmp_host` - SNMP Device. Defaults to `localhost:161`
        * `community` - Community string to query the agent. Defaults to `public`
        * `version` - SNMP Version. Defaults to `2`.
        * `es_host` - ES Connection String. Defaults to `localhost:9200`
        * `es_user` - ES User. Defaults to `elastic`.
        * `use_ssl` - Use SSL for ES. Defaults to `False`.
        * `es_password` - ES Password. Defaults to `changeme`
        * `job_file` - Job File for SNMP Poller. Defaults to `job_file.json`.
        * `poll_rate` - Poll Rate in seconds. Defaults to `30`.
        * `es_template` - ES Template. Defaults to `snmp_template.json`. A sample example has been provided.
        * `log_conf` - Log Conf File. Defaults to `logging.conf`.
        * `pipeline` - Ingest Pipeline - Name Only. Defaults to `None`.

    Example of execution:
    
    `python snmp_es_indexer.py --community password1234 --es_host a988764591d47d33b828dbd6616886fe.eu-west-1.aws.found.io:9243 --es_user elastic --es_password changeme --snmp_host 192.168.1.7 --pipeline elasticON_enrich  --use_ssl`

3. `client_mac_ap_poller.py` - As described here, this script was used to poll an SNMP Ruckus ZD and write the mac to client ips currently connected. Provided for reference as an example of using `snmp_processor.py`.

## Other Files

* `job_file.json` - example job fole for `snmp_es_indexer.py`
* `logging.conf` - Example logging configuration
* `snmp_template.json ` - Example ES Template
* `ZD_MIBS/*` - MIBS Used for Ruckus ZD


## License

See [LICENSE](https://github.com/gingerwizard/ruckus-snmp-poller/LICENSE)
