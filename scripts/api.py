import requests
import gzip 
import json
import os
import argparse
import io

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

def find_local_font(fonts: list, family: str) -> dict:
    for font in fonts:
        if font['id'] == family:
            return font
    return None

def find_font(fonts: list, family: str) -> dict:
    for font in fonts:
        if font['family'] == family:
            return font
    return None

def get_google_font_css(font_family: str, font_variant: str) -> str:
    url = 'http://localhost:3449/internal/gfonts/css'
    params = {
        'family': '{}:{}'.format(font_family, font_variant),
        'display': 'block'
    }
    resp = requests.get(url=url, params=params)
    return resp.text

def get_typography_css(context: dict, typography: dict) -> str:
    font_family = typography['~:font-family']
    font_variant = typography['~:font-variant-id']
    font_style = typography['~:font-style']
    font_weight = typography['~:font-weight']
    local_fonts = context['local-fonts']
    font = find_local_font(local_fonts, font_family)
    if not font:
        return get_google_font_css(font_family, font_variant)

    return ''

def get_typographies_css(context: dict, typographies: dict) -> str:
    css = ''
    for k, v in typographies.items():
        css += get_typography_css(context, v)

    return css

def get_file_typographies(context: dict, project_id: str, file_id: str) -> str:
    file = get_file_completely(context, project_id, file_id)
    return file['~:data']['~:typographies']

def get_file_typographies_as_css(context: dict, project_id: str, file_id: str) -> str:
    typographies = get_file_typographies(context, project_id, file_id)
    if not typographies:
        return ''

    return get_typographies_css(context, typographies)

def get_google_fonts_typographies(filename: str) -> dict:
    file = open(filename,'r')
    payload = json.load(file)
    file.close()
    return payload

class Map(dict): 
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

def map_transit_list(obj: list) -> list:
    return list(map(map_transit, obj))

def map_transit_dict(obj: dict) -> dict:
    mapped = dict()
    for k, v in obj.items():
        mapped[str(k[2:])] = map_transit(v)
    return mapped

def map_transit_value(obj):
    if isinstance(obj, str):
        if obj[0:2] == '~:' or obj[0:2] == '~u':
            return obj[2:]
    return obj

def map_transit(obj):
    if isinstance(obj, dict):
        return Map(map_transit_dict(obj))
    elif isinstance(obj, list):
        return map_transit_list(obj)
    else:
        return map_transit_value(obj)

#
# Main
#
if not os.path.isfile('gfonts.2023.07.07.json'):
    print('Run download-google-fonts.sh first')
    exit(1)

parser = argparse.ArgumentParser()
parser.add_argument('-u','--user',help='User email')
parser.add_argument('-w','--password',help='User password')
parser.add_argument('-f','--file',help='File id')
parser.add_argument('-p','--project',help='Project id')
parser.add_argument('-a','--page',help='Page id')
parser.add_argument('-s','--shape',help='Shape id')
parser.add_argument('-t','--typographies', help='Typographies')
args = parser.parse_args()
    
if not args.user or not args.password:
    print('Invalid user and password')
    exit(1)

if not args.project or not args.file:
    print('Invalid project, file, page or shape ids')
    exit(1)

login = login_with_password(
    args.user, 
    args.password 
)

context = {
    'auth-token': login.cookies['auth-token'],
    'local-fonts': [
        {
            'id': 'sourcesanspro',
            'name': 'Source Sans Pro',
            'family': 'sourcesanspro',
            'variants': [
                {'id': '200', 'name': '200', 'weight': '200', 'style': 'normal', 'suffix': 'extralight'},
                {'id': '200italic', 'name': '200 (italic)', 'weight': '200', 'style': 'italic', 'suffix': 'extralightitalic'},
                {'id': '300', 'name': '300', 'weight': '300', 'style': 'normal', 'suffix': 'light'},
                {'id': '300italic', 'name': '300 (italic)', 'weight': '300', 'style': 'italic', 'suffix': 'lightitalic'},
                {'id': 'regular', 'name': 'regular', 'weight': '400', 'style': 'normal'},
                {'id': 'italic', 'name': 'italic', 'weight': '400', 'style': 'italic'},
                {'id': 'bold', 'name': 'bold', 'weight': 'bold', 'style': 'normal'},
                {'id': 'bolditalic', 'name': 'bold (italic)', 'weight': 'bold', 'style': 'italic'},
                {'id': 'black', 'name': 'black', 'weight': '900', 'style': 'normal'},
                {'id': 'blackitalic', 'name': 'black (italic)', 'weight': '900', 'style': 'italic'}
            ]
        }
    ],
    'google-fonts': get_google_fonts_typographies('gfonts.2023.07.07.json')
}

if args.page and args.shape:
    file = map_transit(get_file_shape(
        context, 
        args.project,
        args.file,
        args.page,
        args.shape
    ))
    print(file.shape.id)
    print(json.dumps(file, indent=2))
elif args.typographies:
    typographies = get_file_typographies_as_css(
        context,
        args.project,
        args.file
    )
    print(typographies)
else:
    print('Not enough arguments')
