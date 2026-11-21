"""State episodes from fresh10-pitch blocks, independent of value-alert clocks."""
from __future__ import annotations

import numpy as np
import pandas as pd


def complete(row):return all(pd.notna(row.get(g+'_state')) and row[g+'_state']>=0 for g in 'ABCD')


def combination(row,minimum_red=2):
    return complete(row) and sum(row[g+'_state']==2 for g in 'ABCD')>=minimum_red and (row['A_state']==2 or row['B_state']==2)


def recovered(row):
    # High cumulative load may remain D-red after measurable performance recovers.
    return complete(row) and row['A_state']==0 and row['B_state']==0 and row['C_state']<2


def replay(points,minimum_red_by_role,validated_by_role):
    out=points.sort_values(['game_pk','team_id','defensive_ordinal']).copy()
    out['cause_run']=0;out['clear_run']=0;out['state_episode_id']=None;out['state_event_entered']=False
    out['nominal_research_alert']=False;out['research_reason']='unknown_evidence';events=[];last_alert={}
    for (game,team,appearance),g in out.groupby(['game_pk','team_id','appearance_id'],sort=False):
        active=None;last_block=None;last_number=None;last_session=None;run=0;clear=0;episode_number=0
        threshold=minimum_red_by_role.get(str(g.role.dropna().iloc[0]) if g.role.notna().any() else 'unknown',2)
        for index,row in g.iterrows():
            if last_session is not None and pd.notna(row.session_id) and row.session_id!=last_session:
                if active:
                    active.update(end_decision_id=row.decision_id,end_reason='new_session_censored');events.append(active);active=None
                last_block=None;last_number=None;run=0;clear=0;last_session=row.session_id
            role=row.role;known=complete(row) and pd.notna(row.block_id)
            if not known:
                run=0;clear=0;out.at[index,'research_reason']='unknown_evidence_pauses_not_recovery'
                if active:out.at[index,'state_episode_id']=active['episode_id']
                continue
            new=row.block_id!=last_block
            if new:
                adjacent=last_number is not None and row.session_id==last_session and row.block_number==last_number+1
                if row.session_id!=last_session and last_session is not None and active:
                    active.update(end_decision_id=row.decision_id,end_reason='new_session_censored');events.append(active);active=None
                run=(run+1 if adjacent else 1) if combination(row,threshold) else 0
                clear=(clear+1 if adjacent else 1) if recovered(row) else 0
                last_block=row.block_id;last_number=row.block_number;last_session=row.session_id
            out.at[index,'cause_run']=run;out.at[index,'clear_run']=clear
            if active and clear>=2:
                active.update(end_decision_id=row.decision_id,end_reason='observed_recovery');events.append(active);active=None;run=0
            if active is None and run>=2:
                episode_number+=1
                active={'episode_id':f'{appearance}:signal:{episode_number}','game_pk':int(game),'team_id':int(team),
                    'appearance_id':appearance,'role':role,'start_decision_id':row.decision_id,'alert_decision_id':None,
                    'end_decision_id':None,'end_reason':None}
                out.at[index,'state_event_entered']=True
            if active:out.at[index,'state_episode_id']=active['episode_id']
            if active is None:reason='awaiting_fresh_block_persistence' if combination(row,threshold) else 'no_state_combination'
            elif not validated_by_role.get(str(role),False):reason='combination_predictive_support_not_established'
            elif active['alert_decision_id'] is not None:reason='dedup_same_state_episode'
            elif row.point_reason!='qualifies':reason='value_gate:'+str(row.point_reason)
            elif (game,team) in last_alert and row.completed_pa_before-last_alert[(game,team)]<=2:reason='team_cooldown'
            else:
                reason='nominal_research_alert';active['alert_decision_id']=row.decision_id
                last_alert[(game,team)]=row.completed_pa_before;out.at[index,'nominal_research_alert']=True
            out.at[index,'research_reason']=reason
        if active:
            active.update(end_decision_id=g.decision_id.iloc[-1],end_reason='last_observed_boundary_censored');events.append(active)
    return out,pd.DataFrame(events,columns=['episode_id','game_pk','team_id','appearance_id','role','start_decision_id','alert_decision_id','end_decision_id','end_reason'])
