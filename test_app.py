import unittest
from unittest.mock import patch, MagicMock
from app import app, verificar_servicio

class TestDashboard(unittest.TestCase):

    def test_servicio_activo(self):
        mock_r = MagicMock()
        mock_r.status_code = 200
        mock_r.elapsed.total_seconds.return_value = 0.123
        with patch("app.requests.get", return_value=mock_r):
            r = verificar_servicio("Test", "https://test.com")
        self.assertTrue(r["activo"])
        self.assertEqual(r["status"], 200)

    def test_servicio_caido_timeout(self):
        import requests as req
        with patch("app.requests.get", side_effect=req.exceptions.Timeout):
            r = verificar_servicio("Test", "https://test.com")
        self.assertFalse(r["activo"])
        self.assertEqual(r["error"], "Timeout")

    def test_endpoint_estado(self):
        mock_r = MagicMock()
        mock_r.status_code = 200
        mock_r.elapsed.total_seconds.return_value = 0.1
        with patch("app.requests.get", return_value=mock_r):
            cliente = app.test_client()
            resp = cliente.get("/api/estado")
        datos = resp.get_json()
        self.assertIn("servicios", datos)
        self.assertIn("timestamp", datos)

if __name__ == "__main__":
    unittest.main(verbosity=2)
