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

    def fake_field(self, query, name, lat, lon, now):
        if name == 'current': return self.weather['current']
        if name == 'hourly': return self.weather['hourly']
        if name == 'daily': return [dict(date='2026-11-07')]*3
        return {'test': name}

    def run_layers(self, weather, now):
        with patch.object(w,'fetch_field',side_effect=self.fake_field) as fetch:
            result=w.refresh_layers(weather, None,38.88,121.53,now)
            return result,[c.args[1] for c in fetch.call_args_list]

    def test_layer_slots_and_merge(self):
        weather,calls=self.run_layers({},self.now)
        self.assertEqual(len(calls),6) # 首次建立各层基线
        weather,calls=self.run_layers(weather,self.now+timedelta(minutes=10))
        self.assertEqual(calls,['current','minute'])
        self.assertEqual(weather['hourly'],self.weather['hourly'])
        self.assertEqual(weather['layers']['medium']['updated_at'],self.now.isoformat())
        weather,calls=self.run_layers(weather,self.now+timedelta(hours=1))
        self.assertEqual(calls,['current','minute','hourly','air'])
        weather,calls=self.run_layers(weather,self.now.replace(hour=17,minute=50))
        self.assertEqual(calls,['current','minute','hourly','air','daily','indices'])
        _,calls=self.run_layers(weather,self.now.replace(hour=17,minute=51))
        self.assertEqual(calls,[])

    def test_failure_preserves_other_layers_and_timestamps(self):
        weather,_=self.run_layers({},self.now)
        def fail(query,name,lat,lon,now):
            if name=='minute': raise RuntimeError()
            return self.fake_field(query,name,lat,lon,now)
        with patch.object(w,'fetch_field',side_effect=fail):
            failed=w.refresh_layers(weather,None,38.88,121.53,self.now+timedelta(minutes=10))
        self.assertEqual(failed['hourly'],weather['hourly'])
        self.assertEqual(failed['minute'],weather['minute'])
        self.assertEqual(failed['fields']['minute']['updated_at'],self.now.isoformat())
        self.assertEqual(failed['fields']['minute']['status'],'error')
        self.assertEqual(failed['status'],'error')
        _,calls=self.run_layers(failed,self.now+timedelta(minutes=11))
        self.assertEqual(calls,[]) # 同时段失败也不会反复调慢层

    def test_six_endpoint_mapping(self):
        calls=[]
        def query(path, params=None):
            calls.append(path)
            row={'obsTime':self.now.isoformat(),'fxTime':self.now.isoformat(),'temp':'15','text':'晴','windSpeed':'10'}
            return {'now':row,'hourly':[row]*24,'daily':[{'fxDate':'2026-11-07','textDay':'晴','tempMin':'5','tempMax':'15'}]*3,'minutely':[]}
        for layer,names in w.LAYERS.items():
            for name in names: w.fetch_field(query,name,38.88,121.53,self.now)
        self.assertEqual(calls,['/v7/weather/now','/v7/minutely/5m','/v7/weather/24h','/airquality/v1/current/38.88/121.53','/v7/weather/3d','/v7/indices/1d'])

    def test_monthly_budget(self):
        weather={}
        counts={name:0 for name in w.LAYERS}
        start=self.now.replace(day=1,hour=0,minute=0)
        for i in range(31*144):
            now=start+timedelta(minutes=10*i)
            weather,calls=self.run_layers(weather,now)
            for name,names in w.LAYERS.items():
                counts[name]+=sum(field in calls for field in names)
        self.assertEqual(counts['fast'],8928)
        self.assertEqual(counts['medium'],1488)
        self.assertLessEqual(counts['slow'],250) # 首次冷启动比稳定运行多2次
        self.assertLessEqual(sum(counts.values()),10666)

    def test_main_merges_root_output(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with patch.object(w,'ROOT',root), patch.object(w.sys,'argv',['fetch']), patch.object(w.os,'environ',MagicMock()), patch.object(w,'client',return_value=None), patch.object(w,'fetch_field',side_effect=self.fake_field):
                self.assertEqual(w.main(),0)
            result=w.json.loads((root/'weather.json').read_text())
            self.assertEqual(result['source'],'qweather')
            self.assertEqual(len(result['layers']),3)
            self.assertIn('alert_text',result)
            self.assertEqual(result['daily'],[{'date':'2026-11-07'}]*3)

    def test_missing_environment_writes_error(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            with patch.object(w,'ROOT',p),patch.object(w.sys,'argv',['fetch']),patch.dict(w.os.environ,{},clear=True),patch.object(w,'get') as request:
                self.assertEqual(w.main(),1)
                request.assert_not_called()
            result=w.json.loads((p/'weather.json').read_text())
            self.assertEqual(result['status'],'error')
            self.assertIn('QWEATHER_API_KEY',result['error'])
            self.assertIn('QWEATHER_API_HOST',result['error'])
            self.assertIsNone(result['updated_at'])

if __name__ == '__main__': unittest.main()
