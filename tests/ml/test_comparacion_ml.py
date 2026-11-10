import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'comparacion_ml_sdn'
sys.path.insert(0, str(SOURCE))
import comparar_modelos_sdn as c
import numpy as np


def crear_csv(folder):
    path = folder/'dataset.csv'
    columns = c.datos_base.FEATURES+c.datos_base.TARGETS+[
        'topologia','particion','run_id','scenario_id','seed','cycle','link_id',
        'feature_start','feature_end','label_start','label_end','measurement_method',
        'probe_loss_scope','sample_status','training_weight']
    rng = np.random.RandomState(52)
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=columns);w.writeheader()
        for pi, partition in enumerate(c.datos_base.PARTICIONES):
            for ti, topology in enumerate(sorted(c.datos_base.TOPOLOGIAS)):
                for i in range(12):
                    x = rng.uniform(.1, 2, 60)
                    x[0] = 5
                    y = [.1*x[1], .2*x[2], .001*x[3], .002*x[4], 5*x[5], 6*x[6]]
                    r = dict(zip(c.datos_base.FEATURES, x))
                    r.update(zip(c.datos_base.TARGETS, y))
                    start = datetime(2026, 1, 1, tzinfo=timezone.utc)+timedelta(seconds=10*i)
                    r.update(topologia=topology,particion=partition,run_id=partition,
                             scenario_id=partition,seed=str(pi),cycle=str(i),link_id='s1-s2',
                             measurement_method='SYNTHETIC_TEST',probe_loss_scope='synthetic',
                             sample_status='synthetic',training_weight=1)
                    for k, dt in zip(['feature_start','feature_end','label_start','label_end'],[0,1,2,3]):
                        r[k] = (start+timedelta(seconds=dt)).isoformat()
                    w.writerow(r)
    (folder/'resumen_final.json').write_text(json.dumps({
        'dataset_final_en_ryu':str(path.resolve()),'cobertura_documentada_total_h':20,
        'nota':'EXCLUSIVAMENTE DATOS SINTETICOS DE PRUEBA'}), encoding='utf-8')
    return path


class ComparisonTest(unittest.TestCase):
    def run_cli(self, *args):
        result = subprocess.run([sys.executable, '-B', str(SOURCE/'comparar_modelos_sdn.py')]+list(args),
                                capture_output=True, text=True, timeout=180)
        return result

    def test_metricas_con_valores_conocidos_y_rango(self):
        y = np.ones((4,6));p = y+2
        data = {'y':y,'metadata':[dict(topologia=t,measurement_method='m',probe_loss_scope='s')
                                  for t in ('NSFNET','NSFNET','GEANT2','GEANT2')]}
        result = c.grupos(data,p)['global']
        for target in c.datos_base.TARGETS:
            self.assertEqual(result[target]['mse'],4)
            self.assertEqual(result[target]['mae'],2)
            self.assertEqual(result[target]['rmse'],2)
        self.assertEqual(result['target_u_to_v_loss_ratio']['predicciones_fuera_rango'],4)

    def test_circuito_completo_cuatro_modelos_y_protecciones(self):
        import joblib
        with tempfile.TemporaryDirectory(dir=None) as td:
            folder = Path(td);path = crear_csv(folder)
            sentinel = folder/'modelo_en_servicio.pkl';sentinel.write_bytes(b'CONSERVAR')
            trained = self.run_cli('entrenar','--dataset',str(path),'--salida',str(folder/'out'))
            self.assertEqual(trained.returncode,0,trained.stdout+trained.stderr)
            out = next((folder/'out').iterdir())
            report = json.loads((out/'comparacion_validation.json').read_text())
            self.assertEqual(set(report['modelos']),set(c.MODELOS))
            self.assertIn(report['seleccion_validation'],c.MODELOS[1:])
            self.assertFalse((out/'comparacion_test.json').exists())
            d = c.datos_base.cargar(str(path))
            model = joblib.load(out/'polinomial.pkl')['modelo']
            np.testing.assert_allclose(model.named_steps['escala'].mean_,d['train']['x'].mean(axis=0))
            self.assertEqual(model.named_steps['polinomio'].n_output_features_,1890)
            args = ['evaluar','--dataset',str(path),'--carpeta',str(out)]
            self.assertNotEqual(self.run_cli(*args).returncode,0)
            self.assertFalse((out/'evaluacion_test_iniciada.json').exists())
            evaluated = self.run_cli(*(args+['--test-ya-examinado']))
            self.assertEqual(evaluated.returncode,0,evaluated.stdout+evaluated.stderr)
            test_report = json.loads((out/'comparacion_test.json').read_text())
            self.assertEqual(test_report['seleccion_previa_validation'],report['seleccion_validation'])
            self.assertEqual(set(test_report['modelos']),set(c.MODELOS))
            self.assertNotEqual(self.run_cli(*(args+['--test-ya-examinado'])).returncode,0)
            self.assertEqual(sentinel.read_bytes(),b'CONSERVAR')
            for split in ('validation','test'):
                with (out/('metricas_'+split+'.csv')).open() as f:
                    rows=list(csv.DictReader(f))
                self.assertTrue(rows)
                self.assertTrue(all(set(['mse','rmse','mae']).issubset(r) for r in rows))

    def test_cargador_rechaza_cruce_de_grupos(self):
        with tempfile.TemporaryDirectory(dir=None) as td:
            path=crear_csv(Path(td))
            text=path.read_text(encoding='utf-8').replace(',validation,validation,validation,',',validation,validation,train,')
            path.write_text(text,encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Cruce de particiones'):
                c.datos_base.cargar(str(path))


if __name__ == '__main__':
    unittest.main()
