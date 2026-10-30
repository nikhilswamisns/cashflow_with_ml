from __future__ import annotations
import argparse
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
import dotenv
import requests

logger = logging.getLogger('zoho.auth')

class ZohoAuthError(Exception):
    pass

class ZohoAuth:

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
        accounts_url: Optional[str] = None,
        env_path: Optional[str | Path] = None,
    ):
        if env_path is not None:
            dotenv.load_dotenv(dotenv_path=env_path)
        else:
            default_env = Path(__file__).parent.parent / '.env'
            if default_env.exists():
                dotenv.load_dotenv(dotenv_path=default_env)
            else:
                dotenv.load_dotenv()

        self.client_id = client_id if client_id is not None else os.getenv('ZOHO_CLIENT_ID', '').strip()
        self.client_secret = client_secret if client_secret is not None else os.getenv('ZOHO_CLIENT_SECRET', '').strip()
        self.refresh_token = refresh_token if refresh_token is not None else os.getenv('ZOHO_REFRESH_TOKEN', '').strip()
        self.accounts_url = (accounts_url or os.getenv('ZOHO_ACCOUNTS_URL', 'https://accounts.zoho.com')).rstrip('/')

        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    def validate_configuration(self, require_refresh_token: bool = True) -> None:
        if not self.client_id:
            raise ZohoAuthError('ZOHO_CLIENT_ID is missing. Please set it in .env or pass it to ZohoAuth.')
        if not self.client_secret:
            raise ZohoAuthError('ZOHO_CLIENT_SECRET is missing. Please set it in .env or pass it to ZohoAuth.')
        if require_refresh_token and not self.refresh_token:
            raise ZohoAuthError('ZOHO_REFRESH_TOKEN is missing. Please generate a grant token and exchange it for a refresh token.')

    def get_access_token(self, force_refresh: bool = False) -> str:
        now = datetime.now(timezone.utc)
        if (
            not force_refresh
            and self._access_token
            and self._token_expiry
            and (self._token_expiry - now).total_seconds() > 300
        ):
            return self._access_token

        self.validate_configuration(require_refresh_token=True)
        self._access_token = self._refresh_access_token()
        return self._access_token

    def _refresh_access_token(self, max_retries: int = 5) -> str:
        token_url = f'{self.accounts_url}/oauth/v2/token'
        params = {
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
        }

        attempt = 0
        backoff = 2.0
        last_err = None

        while attempt < max_retries:
            attempt += 1
            try:
                response = requests.post(token_url, params=params, timeout=30)
                if response.status_code == 200:
                    break
                logger.warning('Token refresh status %d: %s. Retrying (%d/%d)...', response.status_code, response.text, attempt, max_retries)
            except requests.RequestException as e:
                last_err = e
                logger.warning('Network error refreshing token: %s. Retrying (%d/%d) in %.1fs...', e, attempt, max_retries, backoff)
                import time
                time.sleep(backoff)
                backoff *= 2
        else:
            raise ZohoAuthError(f'Network error connecting to Zoho Accounts after {max_retries} attempts: {last_err}') from last_err

        if response.status_code != 200:
            raise ZohoAuthError(f'Failed to refresh Zoho access token: HTTP {response.status_code} - {response.text}')

        data = response.json()
        if 'error' in data:
            err_msg = data.get('error')
            raise ZohoAuthError(f'Zoho OAuth Error: {err_msg}')

        access_token = data.get('access_token')
        if not access_token:
            raise ZohoAuthError('Zoho response did not contain access_token')

        expires_in = int(data.get('expires_in_sec') or data.get('expires_in') or 3600)
        self._access_token = access_token
        self._token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        logger.info('Successfully refreshed Zoho access token (valid for %d seconds)', expires_in)
        return access_token

    def exchange_grant_token(self, grant_token: str, redirect_uri: Optional[str] = None) -> dict[str, Any]:
        self.validate_configuration(require_refresh_token=False)
        token_url = f'{self.accounts_url}/oauth/v2/token'
        params = {
            'code': grant_token.strip(),
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
        }
        if redirect_uri:
            params['redirect_uri'] = redirect_uri

        try:
            response = requests.post(token_url, params=params, timeout=30)
        except requests.RequestException as e:
            raise ZohoAuthError(f'Network error connecting to Zoho Accounts: {e}') from e

        if response.status_code != 200:
            raise ZohoAuthError(f'Failed to exchange grant token: HTTP {response.status_code} - {response.text}')

        data = response.json()
        if 'error' in data:
            raise ZohoAuthError(f"Zoho OAuth exchange error: {data.get('error')}")

        refresh_token = data.get('refresh_token')
        access_token = data.get('access_token')
        if not refresh_token and not access_token:
            raise ZohoAuthError('Invalid response from Zoho OAuth exchange.')

        if refresh_token:
            self.refresh_token = refresh_token
        if access_token:
            expires_in = int(data.get('expires_in_sec') or data.get('expires_in') or 3600)
            self._access_token = access_token
            self._token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        return data

def main():
    parser = argparse.ArgumentParser(description='Zoho OAuth Helper CLI')
    parser.add_argument('--exchange', type=str, help='Grant token / Authorization code to exchange for Refresh Token')
    parser.add_argument('--env-file', type=str, default=None, help='Path to .env file')
    args = parser.parse_args()

    auth = ZohoAuth(env_path=args.env_file)
    if args.exchange:
        print('Exchanging grant token for refresh token...')
        result = auth.exchange_grant_token(args.exchange)
        ref_token = result.get('refresh_token')
        if ref_token:
            print('Successfully obtained Refresh Token.')
            print(f'ZOHO_REFRESH_TOKEN={ref_token}')
            print('\nAdd this value to your .env file as ZOHO_REFRESH_TOKEN.')
        else:
            print('Received response, but no refresh_token was returned.')
            print(f"Details: api_domain={result.get('api_domain')}, expires_in={result.get('expires_in')}")
    else:
        try:
            auth.validate_configuration()
            token = auth.get_access_token()
            print('Configuration verified. Access token obtained successfully.')
        except Exception as e:
            print(f'Error: {e}')

if __name__ == '__main__':
    main()
