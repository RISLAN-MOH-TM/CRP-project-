#!/usr/bin/env python3
"""
Example script to parse JSON scan results

NOTE: This functionality is now integrated into the MCP server!
You can use these MCP tools directly in Claude:
- analyze_all_results() - Get comprehensive statistics
- get_results_for_target(target) - Get all scans for a specific target
- export_results_summary() - Export summary to JSON

This standalone script is kept for manual analysis and automation.
"""

import json
import glob
from collections import Counter, defaultdict
from datetime import datetime

def load_all_results(results_dir='results'):
    """Load all JSON result files"""
    results = []
    for filepath in glob.glob(f'{results_dir}/*.json'):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                results.append(json.load(f))
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
    return results

def print_summary(results):
    """Print summary statistics"""
    total = len(results)
    if total == 0:
        print("No results found!")
        return
    
    successful = sum(1 for r in results if r.get('success'))
    failed = sum(1 for r in results if not r.get('success'))
    rate_limited = sum(1 for r in results if r.get('rate_limited'))
    timed_out = sum(1 for r in results if r.get('timed_out'))
    
    print("=" * 80)
    print("SCAN RESULTS SUMMARY")
    print("=" * 80)
    print(f"Total scans: {total}")
    print(f"Successful: {successful} ({successful/total*100:.1f}%)")
    print(f"Failed: {failed} ({failed/total*100:.1f}%)")
    print(f"Rate limited: {rate_limited}")
    print(f"Timed out: {timed_out}")
    print()

def print_by_tool(results):
    """Print statistics by tool"""
    by_tool = defaultdict(lambda: {'total': 0, 'success': 0, 'failed': 0})
    
    for r in results:
        tool = r.get('tool', 'unknown')
        by_tool[tool]['total'] += 1
        if r.get('success'):
            by_tool[tool]['success'] += 1
        else:
            by_tool[tool]['failed'] += 1
    
    print("SCANS BY TOOL")
    print("-" * 80)
    for tool, stats in sorted(by_tool.items()):
        print(f"{tool:20s}: {stats['total']:3d} total, {stats['success']:3d} success, {stats['failed']:3d} failed")
    print()

def print_top_targets(results, limit=10):
    """Print most scanned targets"""
    targets = Counter(r.get('target', 'unknown') for r in results)
    
    print(f"TOP {limit} TARGETS")
    print("-" * 80)
    for target, count in targets.most_common(limit):
        print(f"{target:50s}: {count:3d} scans")
    print()

def print_failed_scans(results):
    """Print details of failed scans"""
    failed = [r for r in results if not r.get('success')]
    
    if not failed:
        print("No failed scans!")
        return
    
    print(f"FAILED SCANS ({len(failed)} total)")
    print("-" * 80)
    for r in failed:
        print(f"Tool: {r.get('tool')}")
        print(f"Target: {r.get('target')}")
        print(f"Time: {r.get('datetime')}")
        print(f"Error: {r.get('error', 'Unknown error')}")
        if r.get('stderr'):
            print(f"Stderr: {r.get('stderr')[:100]}...")
        print("-" * 80)
    print()

def export_to_csv(results, output_file='scan_results.csv'):
    """Export results to CSV"""
    import csv
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['tool', 'target', 'datetime', 'success', 'return_code', 'error']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        for r in results:
            writer.writerow({
                'tool': r.get('tool', ''),
                'target': r.get('target', ''),
                'datetime': r.get('datetime', ''),
                'success': r.get('success', False),
                'return_code': r.get('return_code', ''),
                'error': r.get('error', '')
            })
    
    print(f"Exported to {output_file}")

def main():
    """Main function"""
    print("\nLoading scan results...\n")
    results = load_all_results()
    
    if not results:
        print("No results found in ./results/ directory")
        return
    
    # Print various statistics
    print_summary(results)
    print_by_tool(results)
    print_top_targets(results)
    print_failed_scans(results)
    
    # Export to CSV
    export_to_csv(results)
    print("\n" + "=" * 80)
    print("Analysis complete!")
    print("=" * 80)

if __name__ == '__main__':
    main()
