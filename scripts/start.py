"""
Production startup script.

Runs migrations using DATABASE_URL from environment, then starts uvicorn.
Done in Python rather than shell to avoid Procfile shell-substitution quirks.
"""

# TEMPORARY DEBUG: print all environment variables the container can see
import os
print("=== ALL ENV VARS THE CONTAINER SEES ===")
for k in sorted(os.environ.keys()):
    v = os.environ[k]
    # Hide secret values but show variable names and lengths
    masked = v[:6] + "..." + str(len(v)) + "chars" if len(v) > 10 else v
    print(f"  {k} = {masked}")
print("=== END ENV VARS ===")
import subprocess
import sys


def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set", file=sys.stderr)
        sys.exit(1)

    port = os.environ.get("PORT", "8000")

    print(f"Starting nest-api in {os.environ.get('ENVIRONMENT', 'unknown')} mode")
    print(f"Database URL detected: {database_url[:30]}... (host portion hidden)")

    # Step 1: Apply migrations
    print("\n>>> Applying migrations...")
    result = subprocess.run(
        ["yoyo", "apply", "--batch", "--database", database_url, "./migrations"],
        check=False,
    )
    if result.returncode != 0:
        print(f"ERROR: Migrations failed with exit code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)
    print(">>> Migrations applied successfully\n")

    # Step 2: Start uvicorn (replaces this process so signals work correctly)
    print(f">>> Starting uvicorn on port {port}...")
    os.execvp(
        "uvicorn",
        ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", port],
    )


if __name__ == "__main__":
    main()
