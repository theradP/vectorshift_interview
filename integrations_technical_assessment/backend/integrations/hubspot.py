import json
import secrets
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio
import base64
import requests
from integrations.integration_item import IntegrationItem
from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

CLIENT_ID = '83ea5a67-40fd-42cc-9c57-1d3c0fae1033' 
CLIENT_SECRET = '427e9e17-a59d-49ee-bce9-c5c611deef34'
REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'

AUTH_URL_BASE = 'https://app.hubspot.com/oauth/authorize'
TOKEN_URL = 'https://api.hubapi.com/oauth/v1/token'
SCOPES = 'crm.objects.contacts.read crm.objects.companies.read crm.objects.deals.read'


async def authorize_hubspot(user_id, org_id):
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode('utf-8')).decode('utf-8')
    
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', json.dumps(state_data), expire=600)
    
    auth_url = f'{AUTH_URL_BASE}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope={SCOPES}&state={encoded_state}'
    
    return auth_url

async def oauth2callback_hubspot(request: Request):
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error_description'))
    
    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode('utf-8'))
    
    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')
    
    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')
    
    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')
    
    async with httpx.AsyncClient() as client:
        response, _ = await asyncio.gather(
            client.post(
                TOKEN_URL,
                data={
                    'grant_type': 'authorization_code',
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET,
                    'redirect_uri': REDIRECT_URI,
                    'code': code
                },
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
            ),
            delete_key_redis(f'hubspot_state:{org_id}:{user_id}'),
        )
    
    await add_key_value_redis(f'hubspot_credentials:{org_id}:{user_id}', json.dumps(response.json()), expire=600)
    
    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)


async def get_hubspot_credentials(user_id, org_id):
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    credentials = json.loads(credentials)
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')
    
    return credentials

def create_integration_item_from_hubspot(record, object_type):
    """Create IntegrationItem from HubSpot record"""
    record_id = record.get('id', '')
    properties = record.get('properties', {})
    
    # Determine name based on object type
    if object_type == 'Contact':
        firstname = properties.get('firstname', '')
        lastname = properties.get('lastname', '')
        name = f"{firstname} {lastname}".strip() or properties.get('email', 'Unknown Contact')
    elif object_type == 'Company':
        name = properties.get('name', 'Unknown Company')
    elif object_type == 'Deal':
        name = properties.get('dealname', 'Unknown Deal')
    else:
        name = 'Unknown Item'
    
    return IntegrationItem(
        id=f"{record_id}_{object_type}",
        name=name,
        type=object_type,
        creation_time=record.get('createdAt'),
        last_modified_time=record.get('updatedAt'),
        url=f"https://app.hubspot.com/contacts/{record.get('portalId', '')}/object/{record_id}" if object_type == 'Contact' else None
    )

def fetch_hubspot_objects(access_token, object_type, properties):
    """Fetch HubSpot objects with pagination"""
    object_type = f"{object_type.lower()}s" if object_type.lower() != 'company' else "companies"
    url = f'https://api.hubapi.com/crm/v3/objects/{object_type}'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    all_records = []
    after = None
    
    while True:
        params = {
            'limit': 100,
            'properties': ','.join(properties)
        }
        if after:
            params['after'] = after
            
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"Error fetching {object_type}s: {response.status_code} - {response.text}")
            break
            
        data = response.json()
        records = data.get('results', [])
        all_records.extend(records)
        
        paging = data.get('paging', {})
        next_page = paging.get('next', {})
        after = next_page.get('after')
        
        if not after:
            break
    
    return all_records

async def get_items_hubspot(credentials) -> list[IntegrationItem]: 
    
    """Fetch HubSpot contacts, companies, and deals"""
    credentials = json.loads(credentials)
    access_token = credentials.get('access_token')
    
    if not access_token:
        raise HTTPException(status_code=400, detail='No access token found in credentials.')
    
    all_items = []
    
    # Define properties to fetch for each object type
    object_configs = {
        'Contact': ['firstname', 'lastname', 'email'],
        'Company': ['name', 'domain'],
        'Deal': ['dealname', 'amount', 'dealstage']
    }
    
    for object_type, properties in object_configs.items():
        try:
            records = fetch_hubspot_objects(access_token, object_type, properties)
            for record in records:
                item = create_integration_item_from_hubspot(record, object_type)
                all_items.append(item)
                print(item.__dict__)
        except Exception as e:
            print(f"Error fetching {object_type}s: {str(e)}")
            continue
    
    print(f'HubSpot integration items: {all_items}')
    return all_items