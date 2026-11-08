"""Guard the authorized teammate integration against accidental strategy edits."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def normalized_strategy(source):
    tree = ast.parse(source)
    tree.body = [node for node in tree.body
                 if not (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == 'info')
                 and not (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ('PARTICIPANT', 'AGENT_NAME') for t in node.targets))]
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()

def test_playing_code_matches_authorized_upstream():
    provenance = json.loads((ROOT / 'PROVENANCE.json').read_text())
    assert normalized_strategy((ROOT / 'agent.py').read_text()) == provenance['strategy_ast_sha256']

def test_preflop_table_matches_authorized_upstream():
    provenance = json.loads((ROOT / 'PROVENANCE.json').read_text())
    assert hashlib.sha256((ROOT / 'data/preflop.npy').read_bytes()).hexdigest() == provenance['preflop_sha256']

def test_team_identity_and_health_counters():
    import agent
    import asyncio
    result = asyncio.run(agent.info())
    assert result['participant'] == 'Starfish'
    assert result['agent_name'] == 'Starfish'
    assert isinstance(result['diagnostics']['fallback_count'], int)
