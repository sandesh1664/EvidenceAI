#!/usr/bin/env python3
"""Publish only fixed job names and GitHub conclusion enums, never raw evidence."""
import json
import os
from pathlib import Path

JOBS = ('secrets', 'application', 'containers', 'dependency-report')
RESULTS = {'success', 'failure', 'cancelled', 'skipped'}


def summarize(needs):
    if set(needs) != set(JOBS):
        raise ValueError('Unexpected CI job set')
    results = {name: needs[name]['result'] for name in JOBS}
    if any(value not in RESULTS for value in results.values()):
        raise ValueError('Unexpected job conclusion')
    return {'version': 1, 'jobs': results, 'release_authorization': 'not_granted',
            'raw_artifacts_uploaded': False}


def main():
    try:
        summary = summarize(json.loads(os.environ['CI_JOB_RESULTS']))
        output = Path('safe-ci-summary')
        output.mkdir(mode=0o700, exist_ok=False)
        content = json.dumps(summary, indent=2)+'\n'
        (output/'status.json').write_text(content)
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as report:
            report.write('CI conclusions only; no release authorization.\n\n```json\n'+content+'```\n')
    except (OSError, KeyError, TypeError, ValueError):
        raise SystemExit('Safe summary generation failed; no raw diagnostic upload permitted') from None


if __name__ == '__main__':
    main()
