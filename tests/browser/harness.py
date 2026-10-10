"""Mock Supabase + helpers for headless-browser tests of index.html."""
import base64
import json
from urllib.parse import parse_qs, urlparse

REF = "mpgkkmkvzgqkvtoearxp"
UID = "00000000-0000-0000-0000-000000000001"


def _jwt():
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{b({'alg': 'HS256', 'typ': 'JWT'})}.{b({'sub': UID, 'role': 'authenticated', 'exp': 4102444800, 'aud': 'authenticated'})}.sig"


USER = {"id": UID, "aud": "authenticated", "role": "authenticated", "email": "tester@example.com",
        "app_metadata": {}, "user_metadata": {}, "created_at": "2026-01-01T00:00:00Z"}
SESSION = {"access_token": _jwt(), "token_type": "bearer", "expires_in": 3600, "expires_at": 4102444800,
           "refresh_token": "r", "user": USER}
ROUTES = [{"id": 1, "land": "ch-hike", "route_type": "national", "name": "Test Route", "description": "d",
           "start_name": "A", "end_name": "C", "total_km": 20}]


def make_stages(n):
    return [{"id": i, "route_id": 1, "land": "ch-hike", "stage_nr": i, "start_name": f"S{i}", "end_name": f"E{i}",
             "via": None, "dist_km": 10, "elev_up": 100, "elev_down": 90, "duration_hrs": 3, "km_asphalt": None,
             "difficulty": "easy", "description": "", "cantons": ["BE"], "arrival_stations": [], "sbb_times": {},
             "osm_id": None, "country": None, "admin1": None, "link_key": None} for i in range(1, n + 1)]


class Mock:
    """Fake Supabase REST/auth. Records every user_state POST in `posts`."""

    def __init__(self, user_state_get=200, user_state_post=201, n_stages=3):
        self.get_status = user_state_get
        self.post_status = user_state_post
        self.n = n_stages
        self.posts = []

    @property
    def rows(self):
        return [r for x in self.posts if x for r in (x if isinstance(x, list) else [x])]

    def handler(self, route):
        req, url, m = route.request, route.request.url, route.request.method
        cors = {"access-control-allow-origin": "*"}
        j = lambda body, code=200: route.fulfill(status=code, content_type="application/json", headers=cors, body=json.dumps(body))
        if m == "OPTIONS":
            return route.fulfill(status=204, headers={**cors, "access-control-allow-headers": "*", "access-control-allow-methods": "*"})
        if "/auth/v1/user" in url:
            return j(USER)
        if "/auth/v1/" in url:
            return j(SESSION)
        if "/rest/v1/routes" in url:
            return j(ROUTES)
        if "/rest/v1/stages" in url:
            q = parse_qs(urlparse(url).query)
            off = int(q.get("offset", ["0"])[0])
            lim = int(q.get("limit", [str(10 ** 9)])[0])
            return j(make_stages(self.n)[off:off + lim])
        if "/rest/v1/user_state" in url:
            if m == "GET":
                return j([] if self.get_status == 200 else {"message": "boom"}, self.get_status)
            self.posts.append(req.post_data_json if req.post_data else None)
            ok = self.post_status < 400
            return route.fulfill(status=self.post_status, content_type="application/json", headers=cors,
                                 body="[]" if ok else json.dumps({"message": "save failed"}))
        if "/rest/v1/user_preferences" in url:
            return j([])
        return route.continue_()
