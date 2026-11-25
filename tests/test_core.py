import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from canvaslink import core

ORIGIN = "https://canvas.example.edu"


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"CANVASLINK_DATA_DIR": self.temp.name})
        self.env.start()
    def tearDown(self):
        self.env.stop(); self.temp.cleanup()
    def configured(self, writes=False):
        core.save_config(ORIGIN, allow_writes=writes)
        core.save_secret("session", {"origin": ORIGIN, "cookies": [
            {"name": "_csrf_token", "value": "fixture", "domain": "canvas.example.edu", "path": "/", "secure": True}]})

    def test_fresh_install_has_no_account(self):
        self.assertEqual(core.Canvas().status(), {"configured": False, "authenticated": False, "needs_setup": True})
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_origin_boundaries(self):
        self.assertEqual(core.validate_origin("https://SCHOOL.example.edu/"), "https://school.example.edu")
        for value in ["http://school.example.edu", "https://user:pass@school.example.edu", "https://school.example.edu/x",
                      "https://school.example.edu?key=x", "https://127.0.0.1", "https://localhost", "https://[::1]",
                      "https://x.local", "https://school.example.edu:8000", "https://evil.example\r\nx", "//school.example.edu"]:
            with self.subTest(value=value), self.assertRaises(ValueError): core.validate_origin(value)

    def test_path_boundaries(self):
        for value in [None,"https://evil.example/x","//evil.example/x","/%252fexample","/%252e%252e/x", "/x\\y", "/x%0d%0aHeader:x", "/x#y", "/api/../logout"]:
            with self.subTest(value=value), self.assertRaises(ValueError):core.validate_path(value)
        self.assertEqual(core.validate_path("/api/v1/courses?include[]=term"), "/api/v1/courses?include[]=term")

    def test_encrypted_storage_tamper(self):
        core.save_secret("bridge-key", "not-a-real-secret")
        path = core.data_dir() / "bridge-key.dpapi"
        self.assertNotIn(b"not-a-real-secret", path.read_bytes())
        self.assertEqual(core.load_secret("bridge-key"), "not-a-real-secret")
        damaged=path.read_bytes();path.write_bytes(damaged[:-1]+bytes([damaged[-1]^1]))
        with self.assertRaises(OSError):core.load_secret("bridge-key")

    def test_origin_change_discards_session(self):
        self.configured();core.save_config("https://another.example.edu")
        self.assertFalse((core.data_dir()/"session.dpapi").exists())
        self.assertTrue(core.Canvas().status()["needs_login"])

    def test_logout_revokes_cached_session(self):
        self.configured();c=core.Canvas();c.reload();core.logout()
        with self.assertRaises(core.LoginRequired):c.reload()

    def test_get_only_routes_and_body_validation(self):
        c=core.Canvas();c.reload=Mock(side_effect=AssertionError("must validate first"))
        for spec in [{"path":"/logout"},{"path":"/api/v1/courses","method":"DELETE"},
                     {"path":"/courses/1","method":"POST","allow_write":True},
                     {"path":"/api/v1/courses","json":{}},{"path":"/api/v1/courses","method":"CONNECT"}]:
            with self.assertRaises(ValueError):c.request(spec)
        c.reload.assert_not_called()

    def test_writes_default_off(self):
        self.configured();c=core.Canvas()
        with patch.object(core,"approve_write") as approve, self.assertRaises(PermissionError):
            c.request({"path":"/api/v1/courses/1","method":"DELETE","allow_write":True})
        approve.assert_not_called()

    def test_write_requires_local_human(self):
        self.configured(True)
        with patch.object(core,"approve_write",return_value=False) as approve, patch.object(core.http.client,"HTTPSConnection") as network:
            with self.assertRaises(PermissionError):
                core.Canvas().request({"path":"/api/v1/courses/1","method":"PUT","json":{"name":"Fixture"},"allow_write":True})
            self.assertIn("Fixture",approve.call_args.args[2]);network.assert_not_called()

    def test_cookie_scope(self):
        jar=core.cookie_jar([{"name":"fixture","value":"value","domain":"canvas.example.edu","path":"/","secure":True}])
        for origin, expected in [(ORIGIN,True),("https://other.example",False),("http://canvas.example.edu",False)]:
            request=core.urllib.request.Request(origin+"/api/v1/courses");jar.add_cookie_header(request)
            self.assertEqual(bool(request.get_header("Cookie")),expected)

    def test_same_origin_pagination_complete(self):
        c=core.Canvas();c.host="canvas.example.edu"
        c.request=Mock(side_effect=[{"status":200,"data":[1],"elapsed_ms":1,"headers":{"Link":'<https://canvas.example.edu/api/v1/x?page=2>; rel="next"'}},
                                   {"status":200,"data":[2],"elapsed_ms":1,"headers":{}}])
        self.assertEqual(c.list_all("/api/v1/x")["items"],[1,2])

    def test_failed_page_is_not_empty_success(self):
        c=core.Canvas();c.host="canvas.example.edu";c.request=Mock(return_value={"status":401,"elapsed_ms":1,"data":{},"headers":{}})
        result=c.list_all("/api/v1/x");self.assertFalse(result["ok"]);self.assertNotIn("items",result)

    def test_external_pagination_and_loops_rejected(self):
        c=core.Canvas();c.host="canvas.example.edu"
        for next_url in ["https://other.example/api/v1/x","https://canvas.example.edu/api/v1/x"]:
            c.request=Mock(return_value={"status":200,"data":[],"elapsed_ms":1,"headers":{"Link":f'<{next_url}>; rel="next"'}})
            with self.assertRaises((ValueError,RuntimeError)):c.list_all("/api/v1/x")

    def test_status_does_not_expose_profile(self):
        c=core.Canvas();c.config={};c.request=Mock(return_value={"status":200,"data":{"id":1,"name":"Fixture Student","email":"fixture@example.edu"}})
        status=c.status();self.assertTrue(status["authenticated"])
        self.assertNotIn("Fixture",json.dumps(status));self.assertNotIn("email",status)

    def test_upstream_redirect_not_followed(self):
        self.configured();c=core.Canvas();r=Mock();r.status=302;r.will_close=True;r.read.return_value=b""
        r.getheader.side_effect=lambda key,default=None:{"Location":"https://external.example/download","Content-Type":"application/octet-stream"}.get(key,default)
        r.info.return_value=core.http.client.HTTPMessage();conn=Mock();conn.getresponse.return_value=r
        with patch.object(core.http.client,"HTTPSConnection",return_value=conn):
            out=c.request({"path":"/files/1/download"})
        self.assertTrue(out["redirect_not_followed"]);self.assertEqual(conn.request.call_count,1)

    def test_http_auth_origin_and_upstream_status(self):
        server=core.ExclusiveServer(("127.0.0.1",0),core.Handler);server.key="fixture-key"
        server.canvas=Mock();server.canvas.request.return_value={"status":401,"needs_login":True}
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            for headers,expected in [({},401),({"Authorization":"Bearer wrong"},401),
                ({"Authorization":"Bearer fixture-key","Origin":"https://evil.example"},403),
                ({"Authorization":"Bearer fixture-key","Host":"evil.example"},403),
                ({"Authorization":"Bearer fixture-key","Sec-Fetch-Site":"same-origin"},403),
                ({"Authorization":"Bearer fixture-key"},200)]:
                conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=5)
                conn.request("GET","/health",headers=headers);res=conn.getresponse();self.assertEqual(res.status,expected);res.read();conn.close()
            conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=5)
            conn.request("POST","/request",json.dumps({"path":"/api/v1/courses"}),{"Authorization":"Bearer fixture-key","Content-Type":"application/json"})
            res=conn.getresponse();self.assertEqual(res.status,200);self.assertEqual(json.loads(res.read())["status"],401);conn.close()
            with self.assertRaises(OSError):core.ExclusiveServer(("127.0.0.1",server.server_port),core.Handler)
        finally:
            server.shutdown();server.server_close();thread.join(2)


if __name__=="__main__":unittest.main()
