import importlib.util
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('weather', 'scripts/fetch_weather.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

class WeatherTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 7, 15, tzinfo=w.TZ)
        row = dict(time=self.now.isoformat(), temperature=15, text='晴', wind_speed=10, gust=None, precipitation=0, probability=None)
        self.weather = dict(source='qweather', current=row.copy(), hourly=[row.copy() for _ in range(24)])

    def test_calm(self):
        a, _ = w.detect(self.weather, {}, self.now)
        self.assertIn('无重要变化', a['text'])

    def test_risk_dedup_escalation_and_resolution(self):
        self.weather['hourly'][0].update(text='雨', probability=65, precipitation=2, wind_speed=40)
        a, state = w.detect(self.weather, {}, self.now)
        self.assertTrue(a['changes'])
        a, state = w.detect(self.weather, state, self.now+timedelta(hours=1))
        self.assertEqual(a['changes'], [])
        self.weather['hourly'][0]['wind_speed'] = 65
        a, state = w.detect(self.weather, state, self.now+timedelta(hours=2))
        self.assertEqual([c['type'] for c in a['changes']], ['wind'])
        self.weather['hourly'][0].update(text='晴', probability=0, precipitation=0, wind_speed=10)
        a, state = w.detect(self.weather, state, self.now+timedelta(hours=3))
        self.assertFalse(state['risks'])
        self.assertIn('无重要变化', a['text'])

    def test_temp_and_snow(self):
        self.weather['hourly'][0].update(temperature=2, text='雪')
        a, _ = w.detect(self.weather, {}, self.now)
        self.assertIn('降温', [c['type'] for c in a['changes']])
        self.assertIn('雪', a['text'])
        self.assertIn('概率未知', a['text'])

    def test_optional_qweather_failures(self):
        def fake(url, params=None):
            if '/weather/now' in url: return {'code':'200','now':{'obsTime':self.now.isoformat(),'temp':'15','text':'晴','windSpeed':'8'}}
            if '/weather/24h' in url: return {'code':'200','hourly':[{'fxTime':self.now.isoformat(),'temp':'15','text':'晴','windSpeed':'8'}]*24}
            if '/weather/3d' in url: return {'code':'200','daily':[{'fxDate':'2026-11-07','textDay':'晴','tempMin':'5','tempMax':'15'}]*3}
            raise RuntimeError('optional unavailable')
        result=w.qweather_data(fake,38.88,121.53)
        self.assertEqual(result['source'], 'qweather')
        self.assertIsNone(result['air'])
        self.assertIsNone(result['current']['gust'])

    def test_failure_overwrites_alert_without_destroying_state(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            (p/'state.json').write_text('{}')
            (p/'latest_alert.txt').write_text('old alert')
            with patch.object(w.sys,'argv',['fetch','--data-dir',temp]), patch.object(w,'ROOT',p), patch.dict(w.os.environ,{},clear=True):
                self.assertEqual(w.main(),1)
            self.assertIn('检查失败', (p/'latest_alert.txt').read_text())
            self.assertEqual((p/'state.json').read_text(),'{}')
            result=w.json.loads((p/'weather.json').read_text())
            self.assertEqual(result['status'],'error')
            self.assertIsNone(result['current'])
            self.assertIn('QWEATHER_API_KEY',result['error'])
            self.assertIn('QWEATHER_API_HOST',result['error'])

    def test_success_writes_root_weather_and_current_risk_summary(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import MagicMock
        self.weather['current']['time'] = datetime.now(w.TZ).isoformat()
        self.weather.update(daily=[{}]*3, minute=None, air=None, indices=None, limitations=[])
        self.weather['hourly'][0].update(text='雪', temperature=2)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with patch.object(w,'ROOT',root), patch.object(w.sys,'argv',['fetch']), patch.object(w.os,'environ',MagicMock()), patch.object(w,'qweather',return_value=self.weather):
                self.assertEqual(w.main(),0)
            result=w.json.loads((root/'weather.json').read_text())
            self.assertEqual(result['status'],'ok')
            self.assertEqual(result['source'],'qweather')
            self.assertIn('雪',result['alert_text'])
            self.assertFalse((root/'data'/'weather.json').exists())
            self.assertEqual(len(result['hourly']),24)

if __name__ == '__main__': unittest.main()
