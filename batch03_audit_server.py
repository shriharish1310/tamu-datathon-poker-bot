"""Read-only post-match diagnostics. Does not intercept timed decisions."""
import agent
from reliability import CORE_KEY
app=agent.app

@app.get('/batch03-metrics')
async def metrics():
    m=agent.MEMORY[CORE_KEY]
    assert 'compute_seconds' in m and 'decisions' in m and 'experiment' in m
    return dict(core_wall_seconds=m.get('compute_seconds'),decisions=m.get('decisions'),
                experiment=m.get('experiment'),scope='Read after all official charged requests; original callbacks unchanged')
