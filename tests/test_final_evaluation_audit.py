"""Research-only safeguards against reporting incomplete or failing final runs."""
from copy import deepcopy
import pytest
from tools.report_final_generalization import validate_matrix, acceptance, seed_interval


def matrix():
    configs=[{'name':f'opponent-{i}'} for i in range(12)]
    plan={'seeds':['a','b','c']}
    rows=[dict(opponent=c['name'],seed=s,num_deals=1000) for c in configs for s in plan['seeds']]
    return rows,plan,configs


def test_matrix_requires_every_planned_slot_once():
    rows,plan,configs=matrix()
    validate_matrix(rows,plan,configs)
    with pytest.raises(ValueError):validate_matrix(rows[:-1],plan,configs)
    with pytest.raises(ValueError):validate_matrix(rows[:-1]+[rows[0]],plan,configs)
    wrong=deepcopy(rows);wrong[0]['seed']='unplanned'
    with pytest.raises(ValueError):validate_matrix(wrong,plan,configs)
    wrong=deepcopy(rows);wrong[0]['num_deals']=999
    with pytest.raises(ValueError):validate_matrix(wrong,plan,configs)


def passing_gate_inputs():
    summary=dict(equally_weighted_match_points=1.,per_opponent=[dict(points=3.,bb_per_paired_deal=1.)]*12,
                 seed_cluster_bb_t_ci95=[.1,2.])
    counters=dict(bank_exhaustions=0,errors=0,forfeits=0,fault_events=0,
                  exception_fallback_decisions=0,disabled_halves=0,logged_fault_events=0,at_or_over_four=0)
    rel={who:deepcopy(counters) for who in ('agent1','agent2')}
    rows=[dict(bot_valid=True,opponent_valid=True,reliability_clean=True,opponent_reliability_clean=True)]*36
    return summary,rel,rows


@pytest.mark.parametrize('participant,counter',[('agent1','exception_fallback_decisions'),
    ('agent2','fault_events'),('agent1','bank_exhaustions'),('agent2','logged_fault_events')])
def test_winning_score_cannot_hide_reliability_failure(participant,counter):
    summary,rel,rows=passing_gate_inputs()
    assert all(acceptance(summary,rel,rows,True,True).values())
    rel[participant][counter]=1
    assert not acceptance(summary,rel,rows,True,True)['zero_reliability_failures']


def test_release_gates_include_strict_runtime_and_profit_requirements():
    summary,rel,rows=passing_gate_inputs()
    rel['agent1']['at_or_over_four']=1
    summary['per_opponent'][0]=dict(points=1.,bb_per_paired_deal=0.)
    summary['seed_cluster_bb_t_ci95']=[0.,2.]
    gates=acceptance(summary,rel,rows,False,False)
    for key in ('candidate_each_half_under_four','each_configuration_at_least_15_points',
                'each_configuration_positive_mean_profit','aggregate_profit_seed_ci_positive',
                'exact_candidate_tests','exact_candidate_official_docker'):
        assert not gates[key]


def test_seed_interval_keeps_three_seed_units():
    assert seed_interval([1.,1.,1.])==[1.,1.]
    with pytest.raises(ValueError):seed_interval([1.]*36)
