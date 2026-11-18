from copy import deepcopy

from app.services.pitcher_decision_ledger import parse_game, statutory_change_status


def fixture():
    def play(ab, inning, pitcher, events, outs, home=0):
        return {"atBatIndex":ab-1,"about":{"inning":inning,"isTopInning":True,"isComplete":True,
                "startTime":f"2024-04-01T18:{ab:02d}:00Z","endTime":f"2024-04-01T18:{ab:02d}:30Z"},
                "matchup":{"pitcher":{"id":pitcher},"batter":{"id":100+ab}},"playEvents":events,
                "count":{"outs":outs},"result":{"type":"atBat","eventType":"field_out","homeScore":home,"awayScore":0},"runners":[]}
    pitch=lambda i,pn: {"index":i,"type":"pitch","isPitch":True,"pitchNumber":pn,"count":{"balls":0,"strikes":1}}
    substitution={"index":1,"type":"action","isPitch":False,"details":{"eventType":"pitching_substitution"},"player":{"id":2},"count":{"balls":1,"strikes":0}}
    return {"gamePk":9,"gameData":{"datetime":{"officialDate":"2024-04-01"},"game":{"scheduledInnings":9}},
            "liveData":{"boxscore":{"teams":{"home":{"team":{"id":10},"pitchers":[1,2],"players":{}},
                                               "away":{"team":{"id":20},"pitchers":[3],"players":{}}}},
                        "plays":{"allPlays":[play(1,1,1,[pitch(0,1)],1),
                            play(2,1,2,[pitch(0,1),substitution,pitch(2,2)],2),
                            play(3,1,2,[pitch(0,1)],3),play(4,2,2,[pitch(0,1)],1)]}}}


def test_mid_pa_actor_and_rule_counts_are_chronological():
    rows=parse_game(2024,fixture())
    events=rows['events']
    assert [r['pitcher_id'] for r in events if r['is_pitch']][:3]==[1,1,2]
    assert rows['plays'][1]['mid_pa_change'] is True
    assert rows['decisions'][1]['observed_change'] is False
    assert rows['decisions'][2]['current_bf']==1
    assert rows['decisions'][2]['statutory_status']=='minimum_batters_not_met'
    assert rows['decisions'][3]['statutory_status']=='allowed'


def test_future_outcomes_do_not_change_earlier_decision_features():
    original=fixture();changed=deepcopy(original)
    changed['liveData']['plays']['allPlays'][-1]['result']['homeScore']=99
    a=parse_game(2024,original);b=parse_game(2024,changed)
    assert a['decisions'][:3]==b['decisions'][:3]
    assert len({r['event_id'] for r in a['events']})==len(a['events'])
    assert all('raw_home_wpa' not in r for r in a['events']+a['decisions'])


def test_legal_rule_distinguishes_inning_end_from_batter_minimum():
    assert statutory_change_status(0,False,True)=='initial_start'
    assert statutory_change_status(1,False,False)=='minimum_batters_not_met'
    assert statutory_change_status(1,True,False)=='allowed'
    assert statutory_change_status(3,False,False)=='allowed'


def test_pinch_runner_inherits_base_without_leaving_old_runner_on_base():
    feed=fixture();plays=feed['liveData']['plays']['allPlays'][:3]
    feed['liveData']['plays']['allPlays']=plays
    plays[0]['result']['eventType']='single';plays[0]['count']['outs']=0
    plays[0]['runners']=[{'details':{'runner':{'id':101},'playIndex':0,'responsiblePitcher':None},'movement':{'end':'1B','isOut':False}}]
    plays[1]['playEvents']=[
        {'index':0,'type':'action','details':{'eventType':'offensive_substitution'},'player':{'id':201},'replacedPlayer':{'id':101}},
        {'index':1,'type':'pitch','isPitch':True,'pitchNumber':1}]
    plays[1]['runners']=[{'details':{'runner':{'id':201},'playIndex':1},'movement':{'start':'1B','end':'2B','isOut':False}}]
    rows=parse_game(2024,feed)
    assert rows['decisions'][2]['base_state']==2
    assert rows['decisions'][2]['base_state_known']
    assert rows['decisions'][1]['batter_id']==102
    assert all(e['batter_id']==102 for e in rows['events'] if e['at_bat_number']==2)


def test_zero_pitch_appearances_are_retained_without_fabricated_pitches():
    feed=fixture();p=feed['liveData']['plays']['allPlays'][0]
    p['playEvents']=[
        {'index':0,'type':'action','details':{'eventType':'pitching_substitution'},'player':{'id':2}},
        {'index':1,'type':'action','details':{'eventType':'pitching_substitution'},'player':{'id':4}},
        {'index':2,'type':'pitch','isPitch':True,'pitchNumber':1}]
    rows=parse_game(2024,feed)
    assert sum(a['zero_pitch'] for a in rows['appearances'])>=2
    assert rows['decisions'][0]['compound_prelude']
    assert next(e for e in rows['events'] if e['is_pitch'])['pitcher_id']==4


def test_seven_inning_game_uses_linescore_rule_and_does_not_invent_extra_runner():
    feed=fixture();feed['liveData']['linescore']={'scheduledInnings':7}
    feed['liveData']['plays']['allPlays']=feed['liveData']['plays']['allPlays'][:1]
    feed['liveData']['plays']['allPlays'][0]['about']['inning']=8
    rows=parse_game(2021,feed)
    assert rows['plays'][0]['scheduled_innings']==7
    assert not rows['decisions'][0]['base_state_known']
