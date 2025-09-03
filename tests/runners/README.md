# Test Runners

This directory contains manual test scripts and debugging runners for development purposes.

## Scripts

### GPU Task Testing
- **test_gpu_task_runner.py** - Test GPU worker tasks (requires Docker containers running)
  ```bash
  python tests/runners/test_gpu_task_runner.py [job_id] [slide_number]
  ```

### TTS Component Testing
- **test_tts_components_runner.py** - Test TTS components individually
- **test_tts_direct.py** - Direct TTS testing without workers
- **test_tts_fix.py** - TTS debugging and fix testing
- **test_tts_isolated.py** - Isolated TTS environment testing

## Prerequisites

Most scripts require:
- Docker containers to be running (`docker-compose up`)
- Database with test data
- MinIO with required files

## Note

These are **development/debugging scripts**, not automated unit tests. For automated testing, see the `tests/unit/` and `tests/integration/` directories.