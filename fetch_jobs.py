#!/usr/bin/env python3
"""Fetch targeted job listings from JSearch API and save to jobs.json."""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.parse import quote_plus
from urllib.error import URLError, HTTPError

API_KEY = os.environ.get("RAPIDAPI_KEY", "")
API_HOST = "jsearch.p.rapidapi.com"
BASE_URL = f"https://{API_HOST}/search"

SEARCHES = [
    {"query": "marketing director women's health", "location": "New York, NY", "remote": False},
    {"query": "marketing director women's health", "location": "United States", "remote": True},
    {"query": "VP marketing mental health", "location": "New York, NY", "remote": False},
    {"query": "VP marketing mental health", "location": "United States", "remote": True},
    {"query": "brand strategy healthcare", "location": "New York, NY", "remote": False},
    {"query": "brand strategy healthcare", "location": "United States", "remote": True},
    {"query": "brand director femtech", "location": "New York, NY", "remote": False},
    {"query": "brand director femtech", "location": "United States", "remote": True},
]

CUTOFF_HOURS = 48


def fetch_jobs_for_query(query, location, remote):
    """Fetch jobs from JSearch API for a single query."""
    remote_filter = "true" if remote else "false"
    url = (
        f"{BASE_URL}?query={quote_plus(query)}"
        f"&page=1&num_pages=1"
        f"&date_posted=week"
        f"&remote_jobs_only={remote_filter}"
    )
    if not remote:
        url += f"&location={quote_plus(location)}"

    req = Request(url)
    req.add_header("x-rapidapi-key", API_KEY)
    req.add_header("x-rapidapi-host", API_HOST)

    try:
        with urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            return data.get("data", [])
    except HTTPError as e:
        print(f"  HTTP {e.code} for query '{query}' (remote={remote}): {e.reason}")
        return []
    except (URLError, TimeoutError, OSError) as e:
        print(f"  Network error for query '{query}': {e}")
        return []


def main():
    if not API_KEY:
        print("Error: RAPIDAPI_KEY environment variable is not set.")
        sys.exit(1)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=CUTOFF_HOURS)
    all_jobs = []
    seen_ids = set()

    for search in SEARCHES:
        label = f"{search['query']} ({'Remote' if search['remote'] else search['location']})"
        print(f"Fetching: {label}")
        results = fetch_jobs_for_query(search["query"], search["location"], search["remote"])
        print(f"  Found {len(results)} results")
        time.sleep(2)  # avoid rate limiting

        for job in results:
            job_id = job.get("job_id", "")
            if not job_id or job_id in seen_ids:
                continue

            posted = job.get("job_posted_at_datetime_utc", "")
            if posted:
                try:
                    posted_dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
                    if posted_dt < cutoff:
                        continue
                except ValueError:
                    pass

            seen_ids.add(job_id)

            is_remote = job.get("job_is_remote", False)
            city = job.get("job_city", "")
            state = job.get("job_state", "")
            location_str = "Remote" if is_remote else f"{city}, {state}".strip(", ")

            salary_min = job.get("job_min_salary")
            salary_max = job.get("job_max_salary")
            salary_period = job.get("job_salary_period", "")
            salary = ""
            if salary_min and salary_max:
                salary = f"${salary_min:,.0f} - ${salary_max:,.0f}"
                if salary_period:
                    salary += f" ({salary_period})"
            elif salary_min:
                salary = f"From ${salary_min:,.0f}"
            elif salary_max:
                salary = f"Up to ${salary_max:,.0f}"

            all_jobs.append({
                "id": job_id,
                "title": job.get("job_title", "Unknown Title"),
                "company": job.get("employer_name", "Unknown Company"),
                "location": location_str,
                "is_remote": is_remote,
                "date_posted": posted,
                "salary": salary,
                "apply_link": job.get("job_apply_link", ""),
                "description_snippet": (job.get("job_description", "") or "")[:200],
                "employer_logo": job.get("employer_logo", ""),
            })

    all_jobs.sort(key=lambda j: j["date_posted"], reverse=True)

    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "job_count": len(all_jobs),
        "jobs": all_jobs,
    }

    with open("jobs.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nDone! Saved {len(all_jobs)} jobs to jobs.json")


if __name__ == "__main__":
    main()
