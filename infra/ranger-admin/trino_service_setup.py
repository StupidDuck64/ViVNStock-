from apache_ranger.model.ranger_service import *
from apache_ranger.client.ranger_client import *
from apache_ranger.model.ranger_policy  import *
import json
import os

## Step 1: create a client to connect to Apache Ranger admin
ranger_url  = os.getenv('RANGER_URL', 'http://localhost:6080')
ranger_auth = (
    os.getenv('RANGER_ADMIN_USER', 'admin'),
    os.getenv('RANGER_ADMIN_PASS', 'Rangeradmin1'),
)

ranger = RangerClient(ranger_url, ranger_auth)
trino_service_file=open('/root/ranger-admin/trino-service.json')
trino_service=json.load(trino_service_file)

service_exist=ranger.get_service('trino')

if service_exist:
    print('Service trino already exists')
    
else:
    print('trino service does not exists. Creating trino service ...')
    ranger.create_service(trino_service)