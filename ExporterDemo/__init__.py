"""
The flask application package.
"""
import yaml, os, argparse, json

from prometheus_client import Gauge, generate_latest, CollectorRegistry

from flask import Flask, Response
import urllib3

# Suppress certificate verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

@app.route('/')
@app.route('/home')
def home():
    output=""
    config=import_config()
    for job in config['scrape_configs']:
        data= getMetricsStatic(job['target'])['data']
        output+=process_data(data, job)

    return Response(output, mimetype='text/plain')


def import_config():
    parser = argparse.ArgumentParser(description="sample argument parser")
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
    for label in job['static_labels']:
        label_names.append(label['name'])
        static_labels.append(label['value'])
    for label in job['labels']:
        label_names.append(label['name'])
    
    for metric in job['metrics']:
        metrics[metric['name']]=Gauge(metric['name'],
                                        metric['description'],
                                        label_names,
                                        registry=registry)
    
    for record in data:
        for metric in job['metrics']:
            label_values=[]
            label_values+=static_labels
            for label in job['labels']:
                label_values.append(record.get(label['name'], ""))
            metrics[metric['name']].labels(*label_values).set(record.get(metric['name'], 0))
    
    return generate_latest(registry).decode('utf-8')

home()

            
