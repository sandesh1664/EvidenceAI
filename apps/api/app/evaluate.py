"""Versioned offline regression runner. Never reads customer evidence or calls hosted APIs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
from uuid import uuid4

from app import evaluate_rag, evaluate_retrieval

VERSION = '2.0'


def latency_summary(values):
    values = sorted(values)
    def percentile(p): return values[math.ceil(len(values)*p)-1]
    return {'sample_count':len(values),'p50_ms':statistics.median(values) if values else None,
            'p95_ms':percentile(.95) if len(values)>=20 else None,
            'p99_ms':percentile(.99) if len(values)>=100 else None,
            'scope':'local synthetic sequential benchmark; not production/load performance'}


def check_thresholds(metrics, thresholds, baseline=None):
    failures=[]
    for name, rule in thresholds.items():
        value=metrics.get(name)
        if value is None or not isinstance(value,(float,int)) or not math.isfinite(value):
            failures.append({'metric':name,'reason':'missing_or_nonfinite'});continue
        if 'min' in rule and value<rule['min']: failures.append({'metric':name,'reason':'below_min','actual':value,'limit':rule['min']})
        if 'max' in rule and value>rule['max']: failures.append({'metric':name,'reason':'above_max','actual':value,'limit':rule['max']})
        if baseline is not None and 'max_drop' in rule:
            previous=baseline.get(name)
            if not isinstance(previous,(int,float)) or not math.isfinite(previous):
                failures.append({'metric':name,'reason':'baseline_missing'})
            elif previous-value>rule['max_drop']:
                failures.append({'metric':name,'reason':'regression','actual':value,'previous':previous})
    return failures


def run(repeat=1):
    profiles={str(dim):[evaluate_retrieval.evaluate(dimensions=dim) for _ in range(repeat)] for dim in (128,256)}
    rag=evaluate_rag.evaluate(extended=True)
    metrics={}
    for dim, runs in profiles.items():
        for name in ('recall_at_k','precision_at_k','mean_reciprocal_rank','ndcg_at_k','empty_result_rate','workspace_isolation_correctness','document_filter_correctness'):
            metrics[f'retrieval_{dim}_{name}']=statistics.mean(r[name] for r in runs)
    for name in ('answer_correctness','citation_reference_validity','citation_gold_support_quality','unsupported_claim_frequency','insufficient_evidence_recall'):
        metrics['rag_'+name]=rag[name]
    metrics['rag_guard_correctness']=sum(g['correct'] for g in rag['guards'])/len(rag['guards'])
    fingerprints={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (evaluate_retrieval.DATASET,evaluate_rag.DATASET,Path(evaluate_retrieval.__file__),Path(evaluate_rag.__file__))}
    # Legacy reports retain their original percentile fields for compatibility. Use only
    # the sample-gated summaries here for performance claims.
    latencies={f'retrieval_{dim}':latency_summary([q['latency_ms'] for r in runs for q in r['queries']]) for dim,runs in profiles.items()}
    latencies['rag']=latency_summary([case['latency_ms'] for case in rag['cases']])
    return {'evaluation_version':VERSION,'dataset_id':'evidenceai-offline-v2','dataset_sha256':fingerprints,
            'executed_at':datetime.now(timezone.utc).isoformat(),'providers':['fake-hash-v1/128','fake-hash-v1/256','mock-extractive-v1'],
            'sample_count':sum(r['query_count'] for runs in profiles.values() for r in runs)+rag['case_count']+len(rag['guards']),
            'semantic_judgment':'unverified','method':'Exact gold labels, quoted-source membership and authorization guards; no semantic entailment judge',
            'metrics':metrics,'latency':latencies,'retrieval_profiles':profiles,'rag':rag,
            'failures':[case for case in rag['cases']+rag['guards'] if not case['correct']]}


def save_report(report, directory):
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid4().hex+'.json')
    with path.open('x') as stream: json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
    return path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path('evaluation/reports'))
    parser.add_argument('--thresholds',type=Path,default=Path('evaluation/thresholds.json'))
    parser.add_argument('--compare',type=Path)
    parser.add_argument('--repeat',type=int,default=1,choices=range(1,21))
    args=parser.parse_args()
    report=run(args.repeat)
    previous=json.loads(args.compare.read_text()) if args.compare else None
    if previous and any(previous.get(key)!=report[key] for key in ('evaluation_version','dataset_sha256','providers')):
        raise SystemExit('Comparison requires identical evaluation version, datasets and providers')
    report['threshold_failures']=check_thresholds(report['metrics'],json.loads(args.thresholds.read_text()),previous['metrics'] if previous else None)
    if previous:
        report['comparison']={key: value-previous['metrics'][key] for key,value in report['metrics'].items() if key in previous['metrics'] and value is not None and previous['metrics'][key] is not None}
    path=save_report(report,args.output_dir)
    print(json.dumps({'report':str(path),'sample_count':report['sample_count'],'metrics':report['metrics'],'threshold_failures':report['threshold_failures']},indent=2))
    if report['threshold_failures']: raise SystemExit(1)


if __name__=='__main__': main()
