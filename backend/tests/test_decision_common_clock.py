import numpy as np
import pandas as pd
from scripts import build_decision_common_clock as q


def test_common_anchor_requires_complete_previous_play_before_official_action():
    f=pd.DataFrame({'anchor_at':[10.,10.,10.,10.,np.nan], 'old_decision_at':[12.,10.,12.,12.,12.],
        'entry_at':[1.,1.,11.,1.,1.],'previous_complete':[True,True,True,False,True],
        'outs':[1]*5,'base_state':[0]*5})
    assert q.anchor_reason(f).tolist()==['included','anchor_not_strictly_before_action','outgoing_not_yet_observed_at_anchor','previous_complete_clock_unknown','previous_complete_clock_unknown']


def test_invalid_anchor_base_state_cannot_be_called_known():
    f=pd.DataFrame({'anchor_at':[10.,10.],'old_decision_at':[12.,12.],'entry_at':[1.,1.],
        'previous_complete':[True,True],'outs':[3,1],'base_state':[0,9]})
    assert (q.anchor_reason(f)=='anchor_state_unknown').all()
