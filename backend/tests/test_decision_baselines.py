import numpy as np
import pandas as pd

from scripts import build_decision_baselines as baseline


def test_legal_transition_checks_runner_conservation_and_terminal_bases():
    assert baseline.legal_transition(0, 0, 1, 0, 0)
    assert baseline.legal_transition(1, 3, 0, 3, 0)
    assert baseline.legal_transition(2, 7, 0, 3, 0)
    assert not baseline.legal_transition(0, 0, 2, 0, 0)
    assert not baseline.legal_transition(1, 0, 0, 0, 0)
    assert not baseline.legal_transition(2, 0, 0, 3, 1)
    assert not baseline.legal_transition(0, 1, 0, 0, 0)


def test_joint_transition_backoff_preserves_legal_probability_sum():
    train = pd.DataFrame({
        'outs': [0, 0, 0], 'base_state': [0, 0, 0], 'extra': [0, 0, 0],
        'target': [0, 0, 3], 'runs_to_pa_end': [0, 0, 1], 'outs_after': [1, 1, 0], 'post_base': [0, 0, 0],
    })
    tables = baseline.fit_transitions(train)
    validation = train.iloc[[0]].copy().reset_index(drop=True)
    validation['extra'] = 1
    probabilities = np.full((1, 9), .1)
    probabilities[0, 0] = .2
    result = baseline.transition_scores(validation, probabilities, tables, True)
    assert np.isclose(result['p'].sum(), 1)
    assert np.isclose(result['runs'][0], 1 / 3)
    assert np.isfinite(result['joint_ll'][0])
    assert np.isclose(result['unsupported_mass'][0], .7)


def test_preprocessing_fit_uses_training_only_and_excludes_identity_labels():
    training = pd.DataFrame({
        'inning': [1., 2., 3., 4.], 'defense_lead': [0., 1., -1., 0.], 'outs': [0., 1., 2., 0.],
        'half': ['top', 'bottom', 'top', 'bottom'], 'base_state': [0, 1, 2, 0], 'extra': [0, 0, 0, 0],
        'scheduled_innings': [9, 9, 9, 9], 'incoming_pitcher_id': [100, 200, 300, 400],
        'observed_pa_result': ['strikeout', 'home_run', 'strikeout', 'home_run'],
    })
    prior = np.full(9, 1 / 9)
    x = baseline.design(training, 'situation', 0, prior)
    assert 'incoming_pitcher_id' not in x and 'observed_pa_result' not in x
    model = baseline.make_model('situation', .001)
    model.fit(x, [0, 3, 0, 3])
    scaler = model[0].named_transformers_['numeric'][1]
    original_mean = scaler.mean_.copy()
    future = training.iloc[[0]].copy()
    future['inning'] = 10000
    future['base_state'] = 7
    p = baseline.probabilities(model, baseline.design(future, 'situation', 0, prior))
    assert np.array_equal(scaler.mean_, original_mean)
    assert p.shape == (1, 9) and np.isclose(p.sum(), 1)
    assert np.all(p > 0)


def test_matchup_pooling_keeps_raw_frame_and_uses_given_training_reference():
    fields = {name: [1.] for name in baseline.LEVELS['matchup'][0] if not name.endswith('_log_n')}
    fields.update({name: ['known'] for name in baseline.LEVELS['matchup'][1]})
    for actor in ('pitcher', 'batter'):
        fields[f'{actor}_own_split_n'] = [1]
        fields[f'{actor}_own_all_n'] = [2]
        fields[f'{actor}_ability_status'] = ['own_split']
    frame = pd.DataFrame(fields)
    before = frame.copy(deep=True)
    x = baseline.design(frame, 'matchup', 20, np.full(9, 1 / 9))
    assert np.isclose(x.pitcher_k_rate.iloc[0], (1 + 20 / 9) / 21)
    pd.testing.assert_frame_equal(before, frame)


def test_nullable_boolean_categorical_missing_stays_explicit_unknown():
    fields = {name: [1., 2.] for name in baseline.LEVELS['workload'][0]}
    fields.update({name: ['known', 'known'] for name in baseline.LEVELS['workload'][1]})
    fields['appeared_earlier_today'] = pd.array([True, None], dtype='boolean')
    design = baseline.design(pd.DataFrame(fields), 'workload', 0, np.full(9, 1 / 9))
    assert design.appeared_earlier_today.tolist() == ['True', 'unknown']


def test_walkoff_filters_excess_non_hr_runs_but_preserves_home_run():
    train = pd.DataFrame({
        'outs': [0, 0, 0], 'base_state': [3, 3, 3], 'extra': [0, 0, 0],
        'target': [4, 4, 3], 'runs_to_pa_end': [1, 2, 3], 'outs_after': [0, 0, 0], 'post_base': [3, 1, 0],
    })
    tables = baseline.fit_transitions(train)
    tied = train.iloc[[0]].reset_index(drop=True).assign(half='bottom', inning=9, scheduled_innings=9, defense_lead=0)
    p = np.zeros((1, 9)); p[0, 4] = 1
    result = baseline.transition_scores(tied, p, tables, True)
    assert result['runs'][0] == 1
    p[0, 4] = 0; p[0, 3] = 1
    assert baseline.transition_scores(tied, p, tables, True)['runs'][0] == 3


def test_batched_values_use_defense_sign_and_terminal_win_probability(monkeypatch):
    train = pd.DataFrame({'outs': [2, 2], 'base_state': [0, 0], 'extra': [0, 0],
        'target': [0, 3], 'runs_to_pa_end': [0, 1], 'outs_after': [3, 2], 'post_base': [0, 0]})
    frame = pd.DataFrame({'outs': [2, 2, 2], 'base_state': [0, 0, 0], 'extra': [0, 0, 0],
        'inning': [9, 9, 9], 'scheduled_innings': [9, 9, 9], 'half': ['top', 'bottom', 'bottom'],
        'defense_lead': [1, 0, 0], 'research_home_we': [.5, .5, .5], 'research_re': [.1, .1, .1],
        'context_model_id': ['research:fixed'] * 3})
    monkeypatch.setattr(baseline.joblib, 'load', lambda _: {'re': {(2, 0, 0): {'mean': .1}}})
    monkeypatch.setattr(baseline, 'we_predict', lambda bundle, post: np.full(len(post), .6))
    p = np.zeros((3, 9)); p[0, 0] = p[1, 0] = p[2, 3] = 1
    wpa, re24 = baseline.expected_values(frame, p, baseline.fit_transitions(train))
    np.testing.assert_allclose(wpa, [.5, -.1, -.5])
    np.testing.assert_allclose(re24, [.1, .1, -.9])
