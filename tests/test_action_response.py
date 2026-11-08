"""Transport optimization must preserve exact successful protocol bodies."""
import pytest
from fastapi.testclient import TestClient
import agent
from game import Action,AgentConfig,Game,make_deal


@pytest.mark.parametrize('action',list(Action))
def test_action_json_bytes_and_headers(monkeypatch,action):
    monkeypatch.setattr(agent,'choose_action',lambda obs,memory:action)
    with TestClient(agent.app) as client:
        assert client.post('/new-half',json={'config':AgentConfig().to_dict()}).status_code==200
        obs=Game(make_deal('b03-runtime-13',0),0,0).observation(0).to_dict()
        response=client.post('/act',json={'observation':obs,'hand_results':[]})
        expected=('{'+'"action":"'+action.name+'","hand_end_errors":[]}').encode()
        assert response.status_code==200 and response.content==expected
        assert response.headers['content-type']=='application/json'
        assert int(response.headers['content-length'])==len(expected)
