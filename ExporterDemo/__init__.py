"""
The flask application package.
"""
import yaml, os, argparse, json, datetime

from prometheus_client import Gauge, generate_latest, CollectorRegistry

from flask import Flask, Response, request
import urllib3

# Suppress certificate verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

@app.route('/')
@app.route('/metrics', methods=['GET'])
def home():
    output=""
    config=import_config()
    for job in config['scrape_configs']:
        data= getMetricsStatic(job['target'])['data']
        output+=process_data(data, job)

    return Response(output, mimetype='text/plain')

@app.route('/metrics/push', methods=['POST'])
def webhook():
    payload=request.data.decode("utf-8").splitlines()
    data=[json.loads(line) for line in payload if line.strip()]
    json_file=getMetricsStatic('pushed_payloads.json')
    json_file['data']+=data
    base_dir = os.path.dirname(__file__)
    file_path = os.path.join(base_dir, 'pushed_payloads.json')
    with open(file_path, 'w') as file:
        json.dump(json_file, file, indent=4)
    return Response(f"POST received at {datetime.datetime.now()}",  status=202)

@app.route('/metrics/reset', methods=['DELETE'])
def deleteWebhookPayloads():
    base_dir = os.path.dirname(__file__)
    file_path = os.path.join(base_dir, 'pushed_payloads.json')
    with open(file_path, 'w') as file:
        json.dump({'data':[]}, file, indent=4)

    return Response(status=204)

def import_config():
    parser = argparse.ArgumentParser(description="parse config")
    parser.add_argument("--config", type=str, default="config.yaml")
    args = parser.parse_args()

    config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), args.config)
    with open (config_path, 'r') as yaml_config:
        config = yaml.safe_load(yaml_config)
    return config

def getMetricsStatic(target):
    # Construct the relative path to the JSON file
    base_dir = os.path.dirname(__file__)
    file_path = os.path.join(base_dir, target)
    with open(file_path) as file:
        data = json.load(file)
    return data

def process_data(data, job):
    label_names=[]
    static_labels=[]
    metrics={}
    registry=CollectorRegistry()
    for label in job.get('static_labels',[]):
        label_names.append(label['name'])
        static_labels.append(label['value'])
    for label in job['labels']:
        if 'rename' in label: label_names.append(label['rename'])
        else: label_names.append(label['name'])
    
    for metric in job['metrics']:
        metrics[metric['name']]=Gauge(metric['name'],
                                        metric['description'],
                                        label_names,
                                        registry=registry)
    for record in data:
        for metric in job['metrics']:
            if 'id_field' in metric and get_nested(record, metric['id_field']) != metric['id']: continue
            label_values=[]
            label_values+=static_labels
            for label in job['labels']:
                label_values.append(get_nested(record, label['name']))
            if 'value_field' in metric:
                value=get_nested(record, metric['value_field'])
            else:
                value=get_nested(record, metric['name'])
            if value is None: value=0
            metrics[metric['name']].labels(*label_values).set(value)
    return generate_latest(registry).decode('utf-8')

def get_nested(record, item):
        try:
            path= item.split('.')
            value=record[path[0]]
            for key in path[1:]:
                value=value[key]
            return value
        except (KeyError, TypeError):
            return None

home()

            
