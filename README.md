# Service Pinger

Quick tool to check if your services are actually up or just pretending to be.

## What it does

Hits a list of URLs or TCP endpoints and tells you:
- Which ones are responding
- Response times
- HTTP status codes
- What's broken when things fail

## Install

```bash
pip install -r requirements.txt
```

Or just run it without requests if you only need TCP checks (but why would you).

## Usage

### Ping a couple URLs

```bash
python service_pinger.py https://google.com https://github.com
```

### Use a services file

Create `services.txt`:

```
https://api.example.com
https://status.example.com
db.example.com:5432
```

Then run:

```bash
python service_pinger.py -f services.txt
```

### All the options

```
python service_pinger.py -f services.txt -t 10 -w 5 -v

-t, --timeout   Timeout in seconds (default: 5)
-w, --workers   Concurrent workers (default: 10)
-v, --verbose   Show error details
--no-color      Disable colors (for CI/CD)
-r, --retries   Max retry attempts on failure (default: 0)
-b, --backoff   Backoff base in seconds: delay = backoff^attempt (default: 2)
```

### Retry with exponential backoff

When a service fails, retry up to N times with increasing delays:

```bash
python service_pinger.py -f services.txt --retries 3 --backoff 2
```

This retries up to 3 times with delays of 1s, 2s, 4s (2^0, 2^1, 2^2).
Results that needed retries show `(N retries)` next to the status.

## Output

```
Pinging 3 service(s) with 10 workers...

Status   Service                        Response   Code
------------------------------------------------------------
✓ google.com                   UP         45.2ms [200]
✓ github.com                   UP         89.1ms [200]
✗ broken.example.com           DOWN           -

============================================================
Summary: 2 up, 0 degraded, 1 down, 0 errors
Total: 3 services checked
```

Exit code is 1 if anything is down or errored, 0 if all good.

## Notes

- HTTP/HTTPS services use the requests library
- Plain host:port uses TCP socket check
- Lines starting with `#` in services file are ignored
- Concurrent by default because waiting sequentially sucks

## Why I made this

Tired of opening 15 browser tabs to check if everything's up after a deploy.
This does it in one command and I can stick it in CI/CD pipelines.
