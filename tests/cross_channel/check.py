import json
import os
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from playwright.sync_api import sync_playwright, expect

base = "http://127.0.0.1:18080"

def api(path, data=None, headers=None):
    req = Request(base + path, data=json.dumps(data).encode() if data else None,
                  headers={"Content-Type":"application/json", **(headers or {})})
    with urlopen(req, timeout=8) as response:
        return json.load(response)

def native(*args):
    return subprocess.check_output([*sys.argv[1:], *args], text=True).strip()

for _ in range(60):
    try:
        if api("/health"): break
    except OSError:
        time.sleep(1)

session = api("/api/login", {"username":"admin","password":os.environ["BININGA_PASS"]})
headers = {"X-Admin-Token":session["token"], "X-CSRF-Token":session["csrf_token"]}

def treat(code):
    entries = api("/api/contacts", headers=headers)["audiences"]
    case, = [entry for entry in entries if entry.get("tracking_code") == code]
    assert api("/api/contacts/update", {"id":case["_id"],"status":"en_cours"},headers)["ok"]

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=os.environ.get("CHROME_BIN"))
    page = browser.new_page()
    page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base + "/") else route.abort())
    page.goto(base + "/",wait_until="domcontentloaded")
    form = page.locator("#form-aud")
    for key,value in {"prenom":"Web","nom":"Test","adresse":"Adresse fictive","telephone":"000000000","raison":"Test isolé"}.items():
        form.locator("[name="+key+"]").fill(value)
    with page.expect_response(lambda r:r.url==base+"/api/contact" and r.request.method=="POST") as reply:
        form.locator("button[type=submit]").evaluate("(button) => button.click()")
    code = reply.value.json()["tracking_code"]
    assert code
    expect(page.locator("#tracking-result")).to_contain_text(code)
    def web_track(ref,expected):
        page.locator("#tracking-code").fill(ref)
        page.locator(".tracking-card button[type=submit]").evaluate("(button) => button.click()")
        expect(page.locator("#tracking-status.ready")).to_contain_text(expected)
        expect(page.locator("#tracking-status.ready")).to_contain_text(ref)
    def check(ref):
        web_track(ref,"Dossier reçu")
        if len(sys.argv)>1: native("track",ref,"Dossier reçu")
        treat(ref)
        web_track(ref,"En cours de traitement")
        if len(sys.argv)>1: native("track",ref,"En cours de traitement")
        print(ref, "Dossier reçu -> En cours de traitement",flush=True)
    check(code)
    if len(sys.argv)>1:
        second = native("create")
        assert second and second != code
        check(second)
    browser.close()
