import json, urllib.request, urllib.parse, urllib.error

class FirebaseSync:
    def __init__(self, config_path):
        with open(config_path, encoding='utf-8') as f:
            self.config = json.load(f)
        self.api_key = self.config.get('apiKey','')
        self.db_url = self.config.get('databaseURL','').rstrip('/')
        self.id_token = None
        self.refresh_token = None
        self.uid = None

    @property
    def ready(self):
        return bool(self.api_key and self.db_url and 'YOUR_' not in self.api_key and 'YOUR_' not in self.db_url)

    def _post(self, url, payload):
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raw=e.read().decode(errors='ignore')
            try:
                msg=json.loads(raw).get('error',{}).get('message',raw)
            except Exception:
                msg=raw or str(e)
            raise RuntimeError(msg)

    def _request(self, method, url, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, method=method, headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else None

    def signup(self, email, password):
        url = f'https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={urllib.parse.quote(self.api_key)}'
        out = self._post(url, {'email':email, 'password':password, 'returnSecureToken':True})
        self._set_auth(out)
        return out

    def login(self, email, password):
        url = f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={urllib.parse.quote(self.api_key)}'
        out = self._post(url, {'email':email, 'password':password, 'returnSecureToken':True})
        self._set_auth(out)
        return out

    def _set_auth(self, out):
        self.id_token = out.get('idToken')
        self.refresh_token = out.get('refreshToken')
        self.uid = out.get('localId')

    def cloud_get(self):
        if not self.uid or not self.id_token: raise RuntimeError('Not logged in')
        url = f'{self.db_url}/users/{urllib.parse.quote(self.uid, safe="")}/appData.json?auth={urllib.parse.quote(self.id_token)}'
        return self._request('GET', url)

    def cloud_put(self, data):
        if not self.uid or not self.id_token: raise RuntimeError('Not logged in')
        url = f'{self.db_url}/users/{urllib.parse.quote(self.uid, safe="")}/appData.json?auth={urllib.parse.quote(self.id_token)}'
        return self._request('PUT', url, data)
