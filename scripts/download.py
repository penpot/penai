import requests
import json
import os
import argparse

def login_with_password(email: str, password: str) -> requests.Response:
    url = 'http://localhost:3449/api/rpc/command/login-with-password'
    json = {
        '~:email': email,
        '~:password': password
    }
    headers = {
        'Content-Type': 'application/transit+json'
    }
    resp = requests.post(url=url, headers=headers, json=json)
    return resp 

def get_file(context: dict, project_id: str, file_id: str) -> dict:
    url = 'http://localhost:3449/api/rpc/command/get-file'
    params = {
        'id': file_id,
        'project-id': project_id,
        'features': [
            'layout/grid',
            'styles/v2',
            'fdata/pointer-map',
            'fdata/objects-map',
            'components/v2',
            'fdata/shape-data-type'
        ],
    }
    cookies = {
        'auth-token': context['auth-token'] 
    }
    resp = requests.get(url=url, params=params, cookies=cookies)
    data = resp.json()
    return data

def get_file_fragment(context: dict, file_id: str, fragment_id: str) -> dict:
    url = 'http://localhost:3449/api/rpc/command/get-file-fragment'
    params = {
        'file-id': file_id,
        'fragment-id': fragment_id 
    }
    cookies = {
        'auth-token': context['auth-token'] 
    }
    resp = requests.get(url=url, params=params, cookies=cookies)
    data = resp.json()
    return data

def get_file_completely(context: dict, project_id: str, file_id: str) -> dict:
    data = get_file(context, project_id, file_id)
    pages_index = data['~:data']['~:pages-index']
    for k, v in pages_index.items():
        fragment_id = v['~#penpot/pointer'][0]
        fragment = get_file_fragment(context, file_id, fragment_id[2:])
        data['~:data']['~:pages-index'][k] = fragment['~:content']

    return data

def get_file_shape(context: dict, project_id: str, file_id: str, page_id: str, shape_id: str) -> dict:
    file = get_file_completely(context, project_id, file_id)
    return file['~:data']['~:pages-index']['~u' + page_id]['~:objects']['~u' + shape_id]

parser = argparse.ArgumentParser()
parser.add_argument('-u','--user',help='User email')
parser.add_argument('-w','--password',help='User password')
parser.add_argument('-f','--file',help='File id')
parser.add_argument('-p','--project',help='Project id')
parser.add_argument('-a','--page',help='Page id')
parser.add_argument('-s','--shape',help='Shape id')
args = parser.parse_args()

if not args.user or not args.password:
    print("Invalid user and password")
    exit(1)

if not args.project or not args.file or not args.page or not args.shape:
    print("Invalid project, file, page or shape ids")
    exit(1)

login = login_with_password(
    args.user, 
    args.password 
)

context = {
    'auth-token': login.cookies['auth-token']
}

file = get_file_shape(
    context, 
    args.project,
    args.file,
    args.page,
    args.shape
)

print(json.dumps(file, indent=2))
