#!/usr/bin/env python3
"""Run system test scenarios with flexible filtering."""
import sys
import subprocess
import argparse
import fnmatch
from pathlib import Path
from typing import List

THIS_DIR = Path(__file__).resolve().parent
SCENARIOS_DIR = THIS_DIR / "scenarios"

SCENARIOS = [
    # Add more scenarios here in order
    SCENARIOS_DIR / "scenario_01_happy_path.py",
    SCENARIOS_DIR / "scenario_02_missing_token.py",
    SCENARIOS_DIR / "scenario_03_insufficient_capability.py",
    SCENARIOS_DIR / "scenario_04_token_expiry.py",
    SCENARIOS_DIR / "scenario_05_token_deletion.py",
    SCENARIOS_DIR / "scenario_06_health_and_swagger.py",
    SCENARIOS_DIR / "scenario_07_multi_user_isolation.py",
    SCENARIOS_DIR / "scenario_08_invalid_metric_names.py",
    SCENARIOS_DIR / "scenario_09_invalid_payloads.py",
    SCENARIOS_DIR / "scenario_10_token_name_conflicts.py",
    SCENARIOS_DIR / "scenario_11_api_capability.py",
    SCENARIOS_DIR / "scenario_12_session_management.py",
    SCENARIOS_DIR / "scenario_13_metric_deletion.py",
    SCENARIOS_DIR / "scenario_14_auth_edge_cases.py",
    SCENARIOS_DIR / "scenario_15_sdk_usage.py",
    SCENARIOS_DIR / "scenario_16_sdk_exceptions.py",
    SCENARIOS_DIR / "scenario_17_dimension_validation.py",
    SCENARIOS_DIR / "scenario_18_sdk_fluent_api.py",
]


def parse_scenario_numbers(spec: str) -> List[int]:
    """Parse scenario number specification like '1,3,5-8,10'.
    
    Returns list of scenario numbers (1-indexed).
    """
    numbers = []
    for part in spec.split(','):
        part = part.strip()
        if '-' in part:
            start, end = part.split('-', 1)
            numbers.extend(range(int(start), int(end) + 1))
        else:
            numbers.append(int(part))
    return sorted(set(numbers))


def filter_scenarios(scenarios: List[Path], 
                     numbers: List[int] = None,
                     pattern: str = None) -> List[Path]:
    """Filter scenarios by numbers or pattern.
    
    Args:
        scenarios: List of all scenario paths
        numbers: List of scenario numbers (1-indexed) to run
        pattern: Glob pattern to match scenario names
    
    Returns:
        Filtered list of scenario paths
    """
    if numbers:
        # Filter by scenario number (1-indexed)
        filtered = []
        for num in numbers:
            if 1 <= num <= len(scenarios):
                filtered.append(scenarios[num - 1])
            else:
                print(f"[WARN] Scenario {num} does not exist (valid range: 1-{len(scenarios)})")
        return filtered
    
    if pattern:
        # Filter by pattern matching
        filtered = []
        for scenario in scenarios:
            if fnmatch.fnmatch(scenario.name, pattern):
                filtered.append(scenario)
        return filtered
    
    # Return all scenarios
    return scenarios


def list_scenarios(scenarios: List[Path]):
    """List all available scenarios."""
    print(f"Available scenarios ({len(scenarios)} total):\n")
    for i, scenario in enumerate(scenarios, 1):
        # Extract description from scenario name
        name_parts = scenario.stem.replace('scenario_', '').replace('_', ' ')
        print(f"  {i:2d}. {scenario.name:<40} - {name_parts}")
    print("\nUsage examples:")
    print("  python run_all.py              # Run all scenarios")
    print("  python run_all.py -n 1         # Run scenario 1")
    print("  python run_all.py -n 1,3,5-8   # Run scenarios 1, 3, 5, 6, 7, 8")
    print("  python run_all.py -p '*sdk*'   # Run scenarios matching '*sdk*'")
    print("  python run_all.py -p '*auth*'  # Run scenarios matching '*auth*'")


def run_scenario(path: Path) -> int:
    """Run a single scenario and return its exit code."""
    print(f"\n== Running {path.name} ==")
    proc = subprocess.run([sys.executable, str(path)], cwd=str(THIS_DIR))
    return proc.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Run system test scenarios with flexible filtering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    Run all scenarios
  %(prog)s -l                 List all available scenarios
  %(prog)s -n 1               Run only scenario 1
  %(prog)s -n 1,3,5           Run scenarios 1, 3, and 5
  %(prog)s -n 1-5             Run scenarios 1 through 5
  %(prog)s -n 1-5,10,15-18    Run scenarios 1-5, 10, and 15-18
  %(prog)s -p '*sdk*'         Run scenarios with 'sdk' in the name
  %(prog)s -p '*auth*'        Run scenarios with 'auth' in the name
  %(prog)s -p 'scenario_01*'  Run scenarios starting with 'scenario_01'
        """
    )
    
    parser.add_argument(
        '-l', '--list',
        action='store_true',
        help='List all available scenarios and exit'
    )
    parser.add_argument(
        '-n', '--numbers',
        type=str,
        metavar='SPEC',
        help='Run specific scenarios by number (e.g., "1,3,5-8")'
    )
    parser.add_argument(
        '-p', '--pattern',
        type=str,
        metavar='PATTERN',
        help='Run scenarios matching glob pattern (e.g., "*sdk*")'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # List scenarios and exit
    if args.list:
        list_scenarios(SCENARIOS)
        return
    
    # Parse scenario numbers if provided
    scenario_numbers = None
    if args.numbers:
        try:
            scenario_numbers = parse_scenario_numbers(args.numbers)
            if args.verbose:
                print(f"Running scenarios: {scenario_numbers}")
        except ValueError as e:
            print(f"[ERROR] Invalid scenario number specification: {e}")
            sys.exit(1)
    
    # Filter scenarios
    selected = filter_scenarios(SCENARIOS, numbers=scenario_numbers, pattern=args.pattern)
    
    if not selected:
        print("[ERROR] No scenarios match the specified criteria")
        print("\nUse -l/--list to see available scenarios")
        sys.exit(1)
    
    # Print summary
    if scenario_numbers or args.pattern:
        print(f"Running {len(selected)} of {len(SCENARIOS)} scenarios:")
        for s in selected:
            scenario_num = SCENARIOS.index(s) + 1
            print(f"  {scenario_num:2d}. {s.name}")
        print()
    
    # Run selected scenarios
    failures = 0
    for scenario in selected:
        rc = run_scenario(scenario)
        if rc != 0:
            print(f"[FAIL] {scenario.name} exited with {rc}")
            failures += 1
    
    # Print results
    if failures:
        print(f"\n[RESULT] {failures} of {len(selected)} scenario(s) failed")
        sys.exit(1)
    
    print(f"\n[RESULT] All {len(selected)} scenario(s) passed")


if __name__ == "__main__":
    main()
