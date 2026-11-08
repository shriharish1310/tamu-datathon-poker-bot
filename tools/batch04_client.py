"""Replay requests from a separate cgroup in the bot's loopback-only netns."""
import argparse,gzip,hashlib,http.client,json,time
from pathlib import Path
WIRE=hashlib.sha256()

def request(conn,path,body=None):
    payload=None if body is None else json.dumps(body,separators=(',',':'))
    began=time.perf_counter();conn.request('GET' if body is None else 'POST',path,payload,{'Content-Type':'application/json'})
    response=conn.getresponse();raw=response.read();data=json.loads(raw);elapsed=time.perf_counter()-began
    if body is not None:WIRE.update(raw+b'\0')
    if response.status!=200:raise RuntimeError((response.status,data))
    return data,elapsed

def main():
    p=argparse.ArgumentParser();p.add_argument('--replay',action='store_true');p.add_argument('--port',type=int,default=5008)
    p.add_argument('--output',default='/out/replay.json');p.add_argument('--health',action='store_true');args=p.parse_args()
    conn=http.client.HTTPConnection('127.0.0.1',args.port,timeout=60)
    for _ in range(300):
        try:request(conn,'/');break
        except (OSError,http.client.HTTPException):
            conn.close()
            time.sleep(.05)
    else:raise RuntimeError('Server not ready')
    if args.health:
        result,_=request(conn,'/');print(json.dumps(result));return
    if not args.replay:
        result,_=request(conn,'/batch04-metrics');print(json.dumps(result));return
    trace=json.loads(gzip.decompress(Path('/research/observations.json.gz').read_bytes()))
    durations=[];answers=[]
    for path,body in trace['requests']:
        data,elapsed=request(conn,path,body);durations.append(elapsed)
        if data.get('hand_end_errors') or data.get('error'):raise RuntimeError(data)
        if path=='/act':answers.append(data['action'])
    result,_=request(conn,'/batch04-metrics')
    result.update(requests=len(durations),request_wall_seconds=sum(durations),
        charged_equivalent_seconds=sum(max(0,t-.001) for t in durations),
        timing_scope='Protocol replay, not a scored official match. Profiling overhead is included when enabled.',
        actions=answers,request_times=durations,response_body_sha256=WIRE.hexdigest())
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
