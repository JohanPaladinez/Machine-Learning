import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT
SPEC = importlib.util.spec_from_file_location('gestion_actual', APP / 'gestion_windows.py')
gestion = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gestion)


class ContractTests(unittest.TestCase):
    def health(self, criteria=None):
        result = {'estado': 'ok', 'servicio': 'SDN/KDN Windows Rutas ML', 'version': '1.0.0'}
        if criteria is not None:
            result['criterios_comparacion'] = criteria
            result['comparacion_modelos_version'] = 1
            result['enrutamiento_icmp_version'] = 1
        return result

    def check_health(self, value):
        with patch.object(gestion, 'build_opener') as opener:
            opener.return_value.open.side_effect = [
                io.BytesIO(json.dumps(value).encode()),
                io.BytesIO(b'<title>SDN / KDN</title><div id="root"></div>'),
            ]
            return gestion.Gestor(APP).comprobar_http()

    def test_old_backend_is_not_reused(self):
        self.assertFalse(self.check_health(self.health()))

    def test_only_two_criteria_are_not_reused(self):
        self.assertFalse(self.check_health(self.health(['capacity', 'ml'])))

    def test_four_criteria_backend_is_reused(self):
        self.assertTrue(self.check_health(self.health(['hops', 'delay', 'capacity', 'ml'])))

    def test_backend_without_real_forwarding_is_not_reused(self):
        health = self.health(['hops', 'delay', 'capacity', 'ml'])
        del health['enrutamiento_icmp_version']
        self.assertFalse(self.check_health(health))

    def test_other_service_is_not_accepted(self):
        health = self.health(['hops', 'delay', 'capacity', 'ml'])
        health['servicio'] = 'otro'
        self.assertFalse(self.check_health(health))


if __name__ == '__main__':
    unittest.main()
