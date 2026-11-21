import numpy as np
import json
from scripts import build_decision_role_models as m


def test_forward_window_requires_full_ten_physical_pitches():
    times=np.arange(1.,13.)
    means,n,last=m.future_windows(times,times,np.array([1.,4.]),10)
    assert means[0]==5.5 and n[0]==10 and last[0]==10
    assert np.isnan(means[1]) and n[1]==0 and np.isnan(last[1])


def test_decline_gate_requires_two_supported_adjacent_bins_and_practical_effect():
    def row(bin_,delta,upper,supported=True):
        return {'axis':'bf','bin':bin_,'delta_vs_first_bin':delta,'simultaneous95_low':delta-1,
            'simultaneous95_high':upper,'supported':supported}
    rows=[row(1,0,0),row(4,-6,-1),row(7,-7,-2)]
    assert m.sustained_pair(rows,'stuff')==[4,7]
    assert m.sustained_pair([rows[0],rows[1],row(10,-7,-2)],'stuff') is None
    assert m.sustained_pair([rows[0],row(4,-1,-.2),row(7,-2,-.3)],'stuff') is None
    assert m.sustained_pair([rows[0],rows[1],row(7,-7,-2,False)],'stuff') is None


def test_risk_feature_whitelist_excludes_current_response_and_future_target():
    assert not any(key.startswith(('response_','future10_','pa_')) for key in m.RISK_NUM+m.RISK_CAT)
    assert 'stuff' not in m.RISK_NUM and 'k' not in m.RISK_NUM
    assert 'past10_stuff' in m.RISK_NUM and 'pitches_3d' in m.RISK_NUM


def test_protocol_survives_json_roundtrip_without_tuple_guard_failure(monkeypatch):
    monkeypatch.setattr(m.b,'digest',lambda path:'test-hash')
    value=m.protocol()
    assert json.loads(json.dumps(value))==value
    assert value['risk_folds'][0]==['2021_late','2021-09-01','2021-09-01','2022-01-01']
