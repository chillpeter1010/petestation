"""Frozen14.2 research-only alert state machine and one-to-one event matching."""
from __future__ import annotations

import numpy as np
import pandas as pd

RULES={'minimum_wpa_gain':.005,'maximum_unsupported_mass':.01,'persistence_boundaries':2,
       'cooldown_defensive_pa':2,'maximum_alerts_per_appearance':1,
       'advance_defensive_pa':2,'advance_seconds':600}


def pa_clock(row):return getattr(row,'completed_pa_before',row.defensive_ordinal)


def qualify(values,rules=RULES):
    """No actual action/event/outcome is consulted by this gate."""
    reason=np.full(len(values),'qualifies',dtype=object)
    checks=[('simulation_censor_or_extrapolation',~values.simulation_supported),
        ('rare_transition_mass',values.maximum_unsupported_mass.gt(rules['maximum_unsupported_mass'])),
        ('below_minimum_gain',values.wpa_delta.lt(rules['minimum_wpa_gain'])),
        ('mc_interval_includes_zero',values.wpa_mc95_low.le(0)),
        ('bootstrap_interval_includes_zero',values.wpa_bootstrap80_low.le(0)),
        ('nonfinite_value',~np.isfinite(values[['wpa_delta','wpa_mc95_low','wpa_bootstrap80_low','maximum_unsupported_mass']]).all(axis=1))]
    for label,mask in reversed(checks):reason[np.asarray(mask)]=label
    return pd.Series(reason,index=values.index)


def issue_alerts(points,rules=RULES):
    """Visit ALL opposing-PA boundaries, including missing/ineligible gaps.

    Persistence resets at a half inning, appearance or skipped/unsupported PA.
    Cooldown covers the next two defensive PAs for that game/team. One emission
    per appearance remains in force after cooldown. No future event data needed.
    """
    out=points.sort_values(['game_pk','team_id','defensive_ordinal']).copy()
    out['run_length']=0;out['alert_emitted']=False;out['alert_reason']=out.point_reason.astype(str)
    for _,g in out.groupby(['game_pk','team_id'],sort=False):
        previous=None;run=0;emitted=set();last_alert=None
        for index,row in g.iterrows():
            if row.point_reason!='qualifies':run=0;previous=row;continue
            adjacent=(previous is not None and previous.point_reason=='qualifies'
                and previous.appearance_id==row.appearance_id and previous.inning==row.inning and previous.half==row.half
                and previous.defensive_ordinal+1==row.defensive_ordinal)
            run=run+1 if adjacent else 1;out.at[index,'run_length']=run
            cooling=last_alert is not None and pa_clock(row)-last_alert<=rules['cooldown_defensive_pa']
            if row.appearance_id in emitted:label='cooldown' if cooling else 'dedup_same_appearance'
            elif run<rules['persistence_boundaries']:label='awaiting_persistence'
            elif cooling:label='cooldown_other_appearance'
            else:
                label='emitted';emitted.add(row.appearance_id);last_alert=pa_clock(row)
                out.at[index,'alert_emitted']=True
            out.at[index,'alert_reason']=label;previous=row
    return out


def eligible_pair(alert,event,rules=RULES):
    if pd.isna(event.outgoing_appearance_id):return None
    if alert.game_pk!=event.game_pk or alert.team_id!=event.team_id or alert.appearance_id!=event.outgoing_appearance_id:return None
    if not np.isfinite(event.event_at) or not np.isfinite(alert.decision_at):return None
    if event.boundary_decision_id==alert.decision_id and event.event_at>=alert.decision_at:return 'same_boundary'
    lead=pa_clock(event)-pa_clock(alert);seconds=event.event_at-alert.decision_at
    if 1<=lead<=rules['advance_defensive_pa'] and 0<seconds<=rules['advance_seconds']:return 'advance_window'
    return None


def match_events(alerts,events,rules=RULES):
    """Chronological alert order, exact first else earliest eligible future event.

    Never choose the nearest event retrospectively. Each alert and official event
    can appear in at most one combined pair. Same-boundary is counted separately.
    """
    assert alerts.decision_id.is_unique and events.event_id.is_unique
    ordered=events.sort_values(['game_pk','at_bat_number','event_index','event_id']);used=set();rows=[]
    for alert in alerts.sort_values(['game_pk','team_id','defensive_ordinal']).itertuples():
        candidates=[]
        group=ordered[ordered.game_pk.eq(alert.game_pk)&ordered.team_id.eq(alert.team_id)&ordered.outgoing_appearance_id.eq(alert.appearance_id)]
        for event in group.itertuples():
            kind=eligible_pair(alert,event,rules)
            if kind is not None and event.event_id not in used:candidates.append((kind,event))
        exact=[x for x in candidates if x[0]=='same_boundary']
        if candidates:
            kind,event=(exact or candidates)[0];used.add(event.event_id)
            rows.append({'decision_id':alert.decision_id,'event_id':event.event_id,'match_kind':kind,
                'lead_defensive_pa':int(pa_clock(event)-pa_clock(alert)),
                'lead_seconds':float(event.event_at-alert.decision_at)})
    pairs=pd.DataFrame(rows,columns=['decision_id','event_id','match_kind','lead_defensive_pa','lead_seconds'])
    assert pairs.decision_id.is_unique and pairs.event_id.is_unique
    return pairs


def unmatched_alert_reason(alert,events,rules=RULES):
    g=events[events.game_pk.eq(alert.game_pk)&events.team_id.eq(alert.team_id)&events.outgoing_appearance_id.eq(alert.appearance_id)]
    if g.empty:return 'no_official_change_for_appearance'
    if any(eligible_pair(alert,event,rules) for event in g.itertuples()):return 'one_to_one_event_consumed'
    if not g[['event_at','defensive_ordinal']].notna().all(axis=1).any():return 'official_clock_or_boundary_unknown'
    g=g.sort_values(['at_bat_number','event_index']);event=next(g.itertuples())
    lead=pa_clock(event)-pa_clock(alert);seconds=event.event_at-alert.decision_at
    if seconds<0 or lead<0:return 'official_event_before_alert'
    if lead==0:return 'no_completed_pa_lead_or_different_boundary'
    if lead>rules['advance_defensive_pa']:return 'outside_2pa_window'
    if seconds>rules['advance_seconds']:return 'outside_600s_window'
    return 'official_clock_or_boundary_unknown'
