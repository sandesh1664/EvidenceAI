#!/usr/bin/env python3
"""Offline release evidence gate. Missing/unknown criteria never become a PASS."""
import argparse
import json
from pathlib import Path

REQUIRED=('container_security','application_security','ai_security','performance','recovery',
          'browser_acceptance','ci_cd','production_environment')


def decision(criteria):
    if any(value not in {'PASS','FAIL','NOT VERIFIED'} for value in criteria.values()):
        raise ValueError('Unknown acceptance classification')
    missing=[key for key in REQUIRED if criteria.get(key)!='PASS']
    return {'release':'BLOCKED' if missing else 'PASS','unmet_criteria':missing}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('report',type=Path)
    args=parser.parse_args();result=decision(json.loads(args.report.read_text())['criteria'])
    print(json.dumps(result,indent=2));raise SystemExit(1 if result['release']=='BLOCKED' else 0)
