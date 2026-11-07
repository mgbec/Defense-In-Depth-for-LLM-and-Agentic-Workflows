"""Run regression cases against a deployed Bedrock guardrail via ApplyGuardrail.

The guardrail id/version are read from SSM Parameter Store (published by Terraform) unless
GUARDRAIL_ID and GUARDRAIL_VERSION are set.

Exit codes: 0 all critical cases pass, 1 a critical case failed, 2 setup error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import boto3
import yaml


def resolve_guardrail(project: str, environment: str, region: str) -> tuple[str, str]:
    gid = os.environ.get("GUARDRAIL_ID")
    ver = os.environ.get("GUARDRAIL_VERSION")
    if gid and ver:
        return gid, ver

    ssm = boto3.client("ssm", region_name=region)
    base = f"/{project}/{environment}/guardrail"
    gid = ssm.get_parameter(Name=f"{base}/id")["Parameter"]["Value"]
    ver = ssm.get_parameter(Name=f"{base}/version")["Parameter"]["Value"]
    return gid, ver


def evaluate(client, gid: str, ver: str, case: dict) -> str:
    text_block: dict = {"text": case["text"]}
    # Prompt attack detection needs the user content tagged as guard content.
    if case["source"] == "INPUT":
        text_block["qualifiers"] = ["guard_content"]

    resp = client.apply_guardrail(
        guardrailIdentifier=gid,
        guardrailVersion=ver,
        source=case["source"],
        content=[{"text": text_block}],
    )
    return "INTERVENED" if resp["action"] == "GUARDRAIL_INTERVENED" else "NONE"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(Path(__file__).with_name("cases.yaml")))
    parser.add_argument("--environment", default=os.environ.get("ENVIRONMENT", "dev"))
    parser.add_argument("--project", default=os.environ.get("PROJECT", "llm-defense"))
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    parser.add_argument("--report", default="guardrail-report.json")
    args = parser.parse_args()

    try:
        gid, ver = resolve_guardrail(args.project, args.environment, args.region)
        cases = yaml.safe_load(Path(args.cases).read_text(encoding="utf-8"))["cases"]
        client = boto3.client("bedrock-runtime", region_name=args.region)
    except Exception as exc:  # noqa: BLE001 - surface any setup failure clearly
        print(f"setup error: {exc}", file=sys.stderr)
        return 2

    print(f"guardrail={gid} version={ver} env={args.environment} cases={len(cases)}\n")

    results, critical_failures, warnings = [], 0, 0
    for case in cases:
        actual = evaluate(client, gid, ver, case)
        passed = actual == case["expect"]
        critical = bool(case.get("critical", True))
        status = "PASS" if passed else ("FAIL" if critical else "WARN")
        if not passed:
            critical_failures += int(critical)
            warnings += int(not critical)
        results.append({**{k: case[k] for k in ("id", "source", "expect", "critical")},
                        "actual": actual, "status": status})
        print(f"[{status}] {case['id']:<35} expected={case['expect']:<10} actual={actual}")

    Path(args.report).write_text(
        json.dumps({"guardrail_id": gid, "version": ver, "results": results}, indent=2),
        encoding="utf-8",
    )
    print(f"\ncritical failures={critical_failures} warnings={warnings}")
    return 1 if critical_failures else 0


if __name__ == "__main__":
    sys.exit(main())
