#!/usr/bin/env python3
"""
CLI script for cleaning up old presentation jobs and their associated files.

This script can be run manually or scheduled as a cron job.

Usage examples:
    python -m app.cli.cleanup_jobs --preview --days 7
    python -m app.cli.cleanup_jobs --execute --days 30 --status completed,failed
    python -m app.cli.cleanup_jobs --specific-jobs 1,2,3,4,5
"""

import argparse
import sys
import os
import json
from datetime import datetime

# Add the parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.cleanup_service import cleanup_service

def main():
    parser = argparse.ArgumentParser(description="Clean up old presentation jobs and files")
    
    # Action group - mutually exclusive
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument("--preview", action="store_true", help="Preview what would be cleaned up")
    action_group.add_argument("--execute", action="store_true", help="Execute cleanup")
    action_group.add_argument("--specific-jobs", type=str, help="Comma-separated list of specific job IDs to cleanup")
    action_group.add_argument("--stats", action="store_true", help="Show cleanup statistics")
    
    # Options
    parser.add_argument("--days", type=int, default=7, help="Clean up jobs older than N days (default: 7)")
    parser.add_argument("--status", type=str, default="completed,failed", 
                       help="Comma-separated list of job statuses to cleanup (default: completed,failed)")
    parser.add_argument("--format", choices=["json", "text"], default="text", 
                       help="Output format (default: text)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Parse status filter
    status_filter = [status.strip() for status in args.status.split(',')]
    
    try:
        if args.preview:
            result = cleanup_service.get_cleanup_preview(
                days_old=args.days,
                status_filter=status_filter
            )
            print_preview(result, args.format, args.verbose)
            
        elif args.execute:
            # Confirm before executing
            if not args.verbose:
                preview = cleanup_service.get_cleanup_preview(
                    days_old=args.days,
                    status_filter=status_filter
                )
                print(f"This will delete {preview['jobs_count']} jobs and their associated files.")
                confirm = input("Are you sure? (y/N): ")
                if confirm.lower() != 'y':
                    print("Cleanup cancelled.")
                    return
            
            result = cleanup_service.cleanup_old_jobs(
                days_old=args.days,
                status_filter=status_filter
            )
            print_cleanup_result(result, args.format, args.verbose)
            
        elif args.specific_jobs:
            job_ids = [int(job_id.strip()) for job_id in args.specific_jobs.split(',')]
            
            # Confirm before executing
            if not args.verbose:
                print(f"This will delete jobs with IDs: {job_ids}")
                confirm = input("Are you sure? (y/N): ")
                if confirm.lower() != 'y':
                    print("Cleanup cancelled.")
                    return
            
            result = cleanup_service.cleanup_specific_jobs(job_ids)
            print_cleanup_result(result, args.format, args.verbose)
            
        elif args.stats:
            stats_7 = cleanup_service.get_cleanup_preview(days_old=7)
            stats_30 = cleanup_service.get_cleanup_preview(days_old=30)
            stats_90 = cleanup_service.get_cleanup_preview(days_old=90)
            
            if args.format == "json":
                print(json.dumps({
                    "7_days": stats_7,
                    "30_days": stats_30,
                    "90_days": stats_90
                }, indent=2))
            else:
                print("Cleanup Statistics:")
                print(f"  Jobs older than 7 days:  {stats_7['jobs_count']}")
                print(f"  Jobs older than 30 days: {stats_30['jobs_count']}")
                print(f"  Jobs older than 90 days: {stats_90['jobs_count']}")
                
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

def print_preview(preview, format_type, verbose):
    """Print cleanup preview results"""
    if format_type == "json":
        print(json.dumps(preview, indent=2))
    else:
        print(f"Cleanup Preview (jobs older than {preview.get('cutoff_date', 'N/A')}):")
        print(f"  Total jobs to cleanup: {preview['jobs_count']}")
        print(f"  Status filter: {preview.get('status_filter', [])}")
        
        if verbose and preview['jobs']:
            print("\nJobs to be cleaned up:")
            for job in preview['jobs']:
                print(f"  - Job ID {job['id']}: {job['status']} (created: {job['created_at']})")
                if job.get('pptx_path'):
                    print(f"    PPTX: {job['pptx_path']}")
                if job.get('video_path'):
                    print(f"    Video: {job['video_path']}")

def print_cleanup_result(result, format_type, verbose):
    """Print cleanup execution results"""
    if format_type == "json":
        print(json.dumps(result, indent=2))
    else:
        print("Cleanup Results:")
        print(f"  Jobs deleted: {result['jobs_deleted']}")
        print(f"  Files deleted: {result['files_deleted']}")
        
        if result['errors']:
            print(f"  Errors: {len(result['errors'])}")
            if verbose:
                for error in result['errors']:
                    print(f"    - {error}")
        
        if verbose and result['jobs_processed']:
            print("\nProcessed jobs:")
            for job in result['jobs_processed']:
                print(f"  - Job ID {job['job_id']}: {job['status']} ({job['files_deleted']} files deleted)")

if __name__ == "__main__":
    main()