#!/usr/bin/env python3
"""Generate custom ratings from normalized per-game statistics."""
import argparse,json,math,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REQUIRED={'id','name','teamId','era','season','positions','points','assists','rebounds','steals','blocks','turnovers','fieldGoalPct','threePct'}
GROUPS={'guard':{'PG','SG'},'wing':{'SG','SF'},'forward':{'SF','PF'},'big':{'PF','C'}}
def clamp(n):return max(40,min(99,round(n)))
def zscore(value,values):
    if len(values)<2 or statistics.pstdev(values)==0:return 0
    return (value-statistics.mean(values))/statistics.pstdev(values)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('input');parser.add_argument('output');parser.add_argument('--overrides',default=ROOT/'scripts/config/manual-rating-overrides.json');parser.add_argument('--config',default=ROOT/'scripts/config/rating-weights.json');parser.add_argument('--report');args=parser.parse_args();raw=json.loads(Path(args.input).read_text());config=json.loads(Path(args.config).read_text());invalid=[];valid=[]
    for row in raw:
        missing=REQUIRED-row.keys()
        if missing:invalid.append({'id':row.get('id'),'missing':sorted(missing)})
        else:valid.append(row)
    pools={group:[p for p in valid if set(p['positions'])&positions] for group,positions in GROUPS.items()}
    def score(row,key):
        groups=[g for g,pos in GROUPS.items() if set(row['positions'])&pos];zs=[zscore(float(row[key]),[float(p[key]) for p in pools[g] if p['season']==row['season']]) for g in groups];return max(config['minimum'],min(config['maximum'],round(config['zScoreCenter']+statistics.mean(zs or[0])*config['zScoreScale'])))
    output=[]
    for row in valid:
        offense=clamp((score(row,'points')*2+score(row,'fieldGoalPct')+score(row,'threePct'))/4);play=clamp((score(row,'assists')*2+99-score(row,'turnovers'))/3);rebound=score(row,'rebounds');defense=clamp((score(row,'steals')+score(row,'blocks'))/2);shooting=clamp((score(row,'fieldGoalPct')+score(row,'threePct'))/2);athletic=clamp((defense+rebound+config['zScoreCenter'])/3);values={'offense':offense,'defense':defense,'shooting':shooting,'playmaking':play,'rebounding':rebound,'athleticism':athletic};overall=clamp(sum(values[k]*config['overallWeights'][k] for k in values));output.append({k:row[k] for k in ['id','name','teamId','era','season','positions']}|{'overall':overall,**values,'ratingMethod':'statistical-position-season-zscore','ratingConfidence':'medium','active':True})
    override_doc=json.loads(Path(args.overrides).read_text()) if args.overrides else {'overrides':{}};overrides=override_doc.get('overrides',override_doc)
    for player in output:
        entry=overrides.get(player['id'])
        if entry:
            if not entry.get('reason') or not entry.get('source'):raise SystemExit(f"Override {player['id']} lacks reason/source")
            player.update(entry.get('fields',{}));player['ratingMethod']='statistical-plus-documented-manual'
    Path(args.output).write_text(json.dumps(output,indent=2)+'\n');report={'invalid':invalid,'generated':len(output)}
    if args.report:Path(args.report).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
if __name__=='__main__':main()
