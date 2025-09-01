# 🧹 Cleanup Management Guide

## Overview

The PPT to Video Generator includes comprehensive cleanup functionality to manage storage and remove old presentation jobs. This system helps maintain optimal performance by cleaning up temporary files, old videos, and failed job artifacts.

## What Gets Cleaned Up

When you run a cleanup operation, the following files and data are removed:

### Files in MinIO Storage
1. **Original PPTX Files** (`/ingest/{uuid}.pptx`)
   - The uploaded PowerPoint presentations
2. **Generated Images** (`/presentations/{uuid}/images/slide-*.png`) 
   - Slide images extracted from presentations
3. **Audio Files** (`/presentations/{job_id}/audio/slide_*.wav`)
   - Synthesized voice audio for each slide
4. **Notes Files** (`/presentations/{job_id}/notes/slide_*.txt`)
   - Extracted speaker notes from slides
5. **Final Videos** (`/output/{job_id}.mp4`)
   - The completed video presentations

### Database Records
- Job entries in the `presentation_jobs` table
- Associated metadata and status information

## Cleanup Methods

### 1. Web API (Recommended)

#### Preview Cleanup
See what would be cleaned without making changes:
```bash
curl "http://localhost:18000/api/cleanup/preview?days_old=7"
```

#### Execute Cleanup by Age
Clean up jobs older than a specific number of days:
```bash
curl -X POST "http://localhost:18000/api/cleanup/execute" \
  -H "Content-Type: application/json" \
  -d '{"days_old": 30, "status_filter": ["failed", "completed"]}'
```

#### Clean Specific Jobs
Remove specific jobs by their IDs:
```bash
curl -X POST "http://localhost:18000/api/cleanup/specific-jobs" \
  -H "Content-Type: application/json" \
  -d '{"job_ids": [1, 2, 3, 4, 5]}'
```

#### Get Statistics
View cleanup statistics and storage usage:
```bash
curl "http://localhost:18000/api/cleanup/stats"
```

### 2. Command Line Interface

The CLI tool is perfect for automation and cron jobs:

#### Basic Usage
```bash
# Preview what would be cleaned
docker exec ppt-api python -m app.cli.cleanup_jobs --preview --days 7

# Execute cleanup with confirmation
docker exec ppt-api python -m app.cli.cleanup_jobs --execute --days 30

# Cleanup specific jobs
docker exec ppt-api python -m app.cli.cleanup_jobs --specific-jobs 1,2,3,4,5

# View statistics
docker exec ppt-api python -m app.cli.cleanup_jobs --stats
```

#### Advanced Options
```bash
# Clean only failed jobs older than 14 days
docker exec ppt-api python -m app.cli.cleanup_jobs \
  --execute --days 14 --status failed

# JSON output for scripts
docker exec ppt-api python -m app.cli.cleanup_jobs \
  --stats --format json

# Verbose output with details
docker exec ppt-api python -m app.cli.cleanup_jobs \
  --preview --days 7 --verbose
```

### 3. Direct Database Query (Advanced)

For advanced users, you can query the database directly:

```sql
-- Connect to database
docker-compose exec postgres psql -U user -d presentation_gen_db

-- View old jobs
SELECT id, status, created_at, s3_pptx_path 
FROM presentation_jobs 
WHERE created_at < NOW() - INTERVAL '7 days'
ORDER BY created_at;

-- Count jobs by status
SELECT status, COUNT(*) 
FROM presentation_jobs 
GROUP BY status;
```

## Cleanup Strategies

### 1. Development/Testing Environment
Clean up frequently to maintain performance:
```bash
# Daily cleanup of failed jobs
docker exec ppt-api python -m app.cli.cleanup_jobs \
  --execute --days 1 --status failed

# Weekly cleanup of completed jobs older than 3 days
docker exec ppt-api python -m app.cli.cleanup_jobs \
  --execute --days 3 --status completed
```

### 2. Production Environment
More conservative cleanup to preserve important data:
```bash
# Monthly cleanup of old failed jobs
docker exec ppt-api python -m app.cli.cleanup_jobs \
  --execute --days 30 --status failed

# Quarterly cleanup of old completed jobs
docker exec ppt-api python -m app.cli.cleanup_jobs \
  --execute --days 90 --status completed
```

### 3. Storage Emergency
When disk space is critically low:
```bash
# Clean all jobs older than 1 day
docker exec ppt-api python -m app.cli.cleanup_jobs \
  --execute --days 1

# Clean specific problematic jobs
docker exec ppt-api python -m app.cli.cleanup_jobs \
  --specific-jobs 1,2,3,4,5,6,7,8,9,10
```

## Automation with Cron Jobs

### Setting up Automated Cleanup

1. **Create cleanup script** (`cleanup-jobs.sh`):
```bash
#!/bin/bash
cd /path/to/ppttovideo

# Daily cleanup of failed jobs
docker exec ppt-api python -m app.cli.cleanup_jobs \
  --execute --days 7 --status failed --format json > /var/log/cleanup-daily.log 2>&1

# Weekly cleanup of completed jobs
if [ $(date +%u) -eq 1 ]; then  # Monday
  docker exec ppt-api python -m app.cli.cleanup_jobs \
    --execute --days 30 --status completed --format json > /var/log/cleanup-weekly.log 2>&1
fi
```

2. **Add to crontab**:
```bash
# Edit crontab
crontab -e

# Add daily cleanup at 2 AM
0 2 * * * /path/to/cleanup-jobs.sh
```

### Monitoring and Alerts

Create monitoring scripts to track storage usage:

```bash
#!/bin/bash
# storage-monitor.sh

STATS=$(docker exec ppt-api python -m app.cli.cleanup_jobs --stats --format json)
JOBS_7_DAYS=$(echo "$STATS" | jq '.["7_days"].jobs_count')

if [ "$JOBS_7_DAYS" -gt 100 ]; then
  echo "Warning: $JOBS_7_DAYS jobs older than 7 days found" | mail -s "PPT Storage Alert" admin@example.com
fi
```

## Safety Features

### Preview Mode
Always preview before executing cleanup:
```bash
# Safe: Shows what would be cleaned
docker exec ppt-api python -m app.cli.cleanup_jobs --preview --days 30

# Safe: API preview
curl "http://localhost:18000/api/cleanup/preview?days_old=30"
```

### Confirmation Prompts
CLI tool includes interactive confirmation:
```bash
docker exec ppt-api python -m app.cli.cleanup_jobs --execute --days 30
# Output: This will delete 5 jobs and their associated files.
# Output: Are you sure? (y/N):
```

### Status Filtering
Default cleanup only affects completed or failed jobs:
- ✅ **Safe to clean**: `completed`, `failed`
- ❌ **Never cleaned**: `pending`, `processing_slides`, `synthesizing_audio`, `assembling_video`

## Troubleshooting

### Common Issues

**❌ "Permission denied" errors:**
```bash
# Check container is running
docker ps | grep ppt-api

# Check MinIO connectivity
docker exec ppt-api curl -I http://minio:9000/minio/health/live
```

**❌ Database connection errors:**
```bash
# Check PostgreSQL connection
docker exec ppt-api python -c "from app.db.session import SessionLocal; db = SessionLocal(); print('DB OK')"
```

**❌ Files not being deleted:**
```bash
# Check MinIO console for manual verification
open http://localhost:19001

# Check file permissions in MinIO
docker exec ppt-minio ls -la /data
```

### Recovery

If cleanup fails partially:

1. **Check cleanup logs:**
```bash
# View API logs
docker-compose logs api | grep cleanup

# Check specific job status
curl "http://localhost:18000/api/presentations/status/JOB_ID"
```

2. **Manual file cleanup:**
```bash
# List MinIO objects
docker exec ppt-minio mc ls local/presentations/

# Remove specific object
docker exec ppt-minio mc rm local/presentations/old-file.png
```

3. **Database cleanup:**
```sql
-- Remove orphaned job records
DELETE FROM presentation_jobs WHERE id IN (1, 2, 3);
```

## Performance Considerations

### Large Cleanup Operations
For cleaning many jobs at once:

```bash
# Process in smaller batches
for i in {1..10}; do
  docker exec ppt-api python -m app.cli.cleanup_jobs \
    --specific-jobs $(seq $((i*10-9)) $((i*10)) | tr '\n' ',' | sed 's/,$//') \
    --format json
  sleep 5  # Pause between batches
done
```

### Storage Monitoring
Monitor disk usage during cleanup:

```bash
# Check available space
df -h

# Monitor MinIO usage
docker exec ppt-minio du -sh /data/*

# Check container resource usage
docker stats ppt-api ppt-minio
```

## Best Practices

### 1. Regular Maintenance
- Run cleanup weekly for development environments
- Run cleanup monthly for production environments
- Always preview before executing large cleanup operations

### 2. Storage Monitoring
- Set up disk space alerts at 80% capacity
- Monitor job creation vs. cleanup ratios
- Track cleanup statistics over time

### 3. Data Retention
- Keep completed jobs for at least 30 days
- Remove failed jobs more aggressively (7 days)
- Backup important presentations before cleanup

### 4. Automation
- Use cron jobs for regular cleanup
- Implement monitoring and alerting
- Log all cleanup operations for auditing

---

**🧹 Keep your PPT to Video Generator running smoothly with regular cleanup! ✨**