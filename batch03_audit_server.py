"""Read-only post-match diagnostics. Does not intercept timed decisions."""
import agent
app=agent.app

@app.get('/batch03-metrics')
async def metrics():
    m=agent.MEMORY
    return dict(core_wall_seconds=m.get('compute_seconds'),decisions=m.get('decisions'),
                experiment=m.get('experiment'),scope='Read after all official charged requests; original callbacks unchanged')
