from __future__ import annotations
import argparse
import logging
import os
import time
from typing import Any, Optional
import requests
from zoho.auth import ZohoAuth, ZohoAuthError

logger = logging.getLogger('zoho.client')

class ZohoAPIError(Exception):
    def __init__(self, message: str, code: Optional[int] = None, response_data: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.response_data = response_data

class ZohoRateLimitError(ZohoAPIError):
    pass

class ZohoPermissionError(ZohoAPIError):
    pass

class ZohoNotFoundError(ZohoAPIError):
    pass

class ZohoValidationError(ZohoAPIError):
    pass

class ZohoClient:

    def __init__(
        self,
        auth: Optional[ZohoAuth] = None,
        org_id: Optional[str] = None,
        api_base_url: Optional[str] = None,
        timeout: int = 30,
    ):
        self.auth = auth or ZohoAuth()
        self.org_id = (org_id or os.getenv('ZOHO_ORG_ID', '')).strip()
        self.api_base_url = (api_base_url or os.getenv('ZOHO_API_BASE_URL', 'https://www.zohoapis.com/books/v3')).rstrip('/')
        self.timeout = timeout

    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        data: Optional[Any] = None,
        retry_on_auth_fail: bool = True,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        endpoint = endpoint.lstrip('/')
        url = f'{self.api_base_url}/{endpoint}'

        req_params: dict[str, Any] = dict(params or {})
        if self.org_id and 'organizations' not in endpoint and 'organization_id' not in req_params:
            req_params['organization_id'] = self.org_id

        attempt = 0
        backoff = 1.0

        while attempt < max_retries:
            attempt += 1
            token = self.auth.get_access_token(force_refresh=False)
            headers = {
                'Authorization': f'Zoho-oauthtoken {token}',
                'Content-Type': 'application/json;charset=UTF-8',
            }

            try:
                response = requests.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    params=req_params,
                    json=json_data,
                    data=data,
                    timeout=self.timeout,
                )
            except requests.RequestException as e:
                if attempt >= max_retries:
                    raise ZohoAPIError(f'Network connection to Zoho API failed: {e}') from e
                time.sleep(backoff)
                backoff *= 2
                continue

            if response.status_code == 401 and retry_on_auth_fail:
                logger.warning('Received 401 from Zoho API. Forcing access token refresh and retrying...')
                self.auth.get_access_token(force_refresh=True)
                retry_on_auth_fail = False
                continue

            if response.status_code == 429:
                if attempt >= max_retries:
                    raise ZohoRateLimitError(f'Zoho API rate limit exceeded: {response.text}', code=429)
                sleep_time = backoff
                logger.warning('Rate limited by Zoho API. Sleeping for %.1f seconds...', sleep_time)
                time.sleep(sleep_time)
                backoff *= 2
                continue

            if response.status_code == 403:
                raise ZohoPermissionError(f'Zoho API permission error (check OAuth scopes / org access): {response.text}', code=403)

            if response.status_code == 404:
                raise ZohoNotFoundError(f'Zoho resource not found at {endpoint}: {response.text}', code=404)

            try:
                resp_json = response.json()
            except ValueError:
                if response.status_code >= 400:
                    raise ZohoAPIError(f'Zoho API error HTTP {response.status_code}: {response.text}', code=response.status_code)
                return {'raw': response.text, 'status_code': response.status_code}

            code = resp_json.get('code')
            if code is not None and code != 0:
                msg = resp_json.get('message', 'Unknown Zoho API error')
                if response.status_code == 400 or code in (1000, 1001, 1002):
                    raise ZohoValidationError(f'Zoho validation error: {msg} (code: {code})', code=code, response_data=resp_json)
                raise ZohoAPIError(f'Zoho API error: {msg} (code: {code})', code=code, response_data=resp_json)

            if response.status_code >= 400:
                raise ZohoAPIError(f"Zoho API error HTTP {response.status_code}: {resp_json.get('message', response.text)}", code=response.status_code, response_data=resp_json)

            return resp_json

        raise ZohoAPIError(f'Failed to complete request to {endpoint} after {max_retries} attempts.')

    def get(self, endpoint: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return self.request('GET', endpoint, params=params)

    def post(self, endpoint: str, json_data: Optional[Any] = None, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return self.request('POST', endpoint, params=params, json_data=json_data)

    def put(self, endpoint: str, json_data: Optional[Any] = None, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return self.request('PUT', endpoint, params=params, json_data=json_data)

    def delete(self, endpoint: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return self.request('DELETE', endpoint, params=params)

    def get_organizations(self) -> list[dict[str, Any]]:
        resp = self.get('organizations')
        return resp.get('organizations', [])

def main():
    parser = argparse.ArgumentParser(description='Zoho Books API Client CLI')
    parser.add_argument('--list-orgs', action='store_true', help='List all organizations accessible with current credentials')
    args = parser.parse_args()

    client = ZohoClient()
    if args.list_orgs:
        try:
            orgs = client.get_organizations()
            print(f'Found {len(orgs)} organizations:')
            for o in orgs:
                org_id = o.get('organization_id')
                name = o.get('name')
                is_default = o.get('is_default_org', False)
                print(f" - {name} (ID: {org_id}) {'[DEFAULT]' if is_default else ''}")
            print('\nSet ZOHO_ORG_ID in .env to your desired organization ID.')
        except Exception as e:
            print(f'Error listing organizations: {e}')

if __name__ == '__main__':
    main()
