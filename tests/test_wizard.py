import io
import os
import unittest

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.pop("ANTHROPIC_API_KEY", None)

from app import create_app  # noqa: E402

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
       b"\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82")


class WizardTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def _create(self):
        return self.client.post("/wizard/new", data={
            "name": "텀블러", "category": "주방", "price": "19,900원",
            "features": "보온\n보냉", "specs": "용량: 500ml", "tone": "premium", "theme": "navy",
            "images": (io.BytesIO(PNG), "a.png"),
        }, content_type="multipart/form-data")

    def test_flow(self):
        r = self._create()
        self.assertEqual(r.status_code, 302)
        page_url = r.headers["Location"]
        self.assertEqual(self.client.get(page_url).status_code, 200)
        prev = self.client.get(page_url + "/preview").get_data(as_text=True)
        self.assertIn("텀블러", prev)
        self.assertIn("POINT 02", prev)
        exp = self.client.get(page_url + "/export")
        self.assertIn("data:image/png;base64", exp.get_data(as_text=True))
        self.assertIn("attachment", exp.headers["Content-Disposition"])

    def test_requires_name(self):
        r = self.client.post("/wizard/new", data={"name": ""})
        self.assertEqual(r.status_code, 400)

    def test_edit_and_delete(self):
        url = self._create().headers["Location"]
        self.client.post(url, data={"headline": "새 카피", "feature_title": ["A"], "feature_desc": ["설명"]})
        self.assertIn("새 카피", self.client.get(url + "/preview").get_data(as_text=True))
        self.assertEqual(self.client.post(url + "/delete").status_code, 302)
        self.assertEqual(self.client.get(url).status_code, 404)


if __name__ == "__main__":
    unittest.main()
