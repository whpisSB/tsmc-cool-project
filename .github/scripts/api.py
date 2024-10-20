#!/usr/bin/env python3

import subprocess
import sys
import json
import requests
from gen_review import get_review_summary


def get_diff_and_reviewers(token, repo, pr_num):
    cmd = f"""
    curl -L \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer {token}" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    https://api.github.com/repos/{repo}/pulls/{pr_num}
    """
    res = subprocess.run(cmd, capture_output=True, shell=True)
    json_res = json.loads(res.stdout.decode())

    head_sha = json_res["head"]["sha"]
    base_sha = json_res["base"]["sha"]

    diff = extract_diff(head_sha, base_sha)
    pr_url = json_res["html_url"]

    if len(json_res["requested_reviewers"]) == 0:
        reviewers = ""
    else:
        reviewers = json_res["requested_reviewers"][0]["login"]

    return pr_url, diff, reviewers


def get_contributors(token, repo, pr_num):
    commit_count, commit_stat = {}, {}

    cmd = f"""
    curl -L \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer {token}" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    https://api.github.com/repos/{repo}/pulls/{pr_num}/commits
    """
    res = subprocess.run(cmd, capture_output=True, shell=True)
    json_res = json.loads(res.stdout.decode())

    for commit in json_res:
        url = commit["url"]
        cmd = f"""
        curl -L \
        -H "Accept: application/vnd.github+json" \
        -H "Authorization: Bearer {token}" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        {url}
        """
        res = subprocess.run(cmd, capture_output=True, shell=True)
        _json_res = json.loads(res.stdout.decode())
        try:
            author = _json_res["author"]["login"]
            commit_count[author] = commit_count.get(author, 0) + 1
            author_stat = commit_stat.get(
                author, {"additions": 0, "deletions": 0, "total": 0}
            )

            for key in author_stat.keys():
                author_stat[key] += _json_res["stats"][key]

            commit_stat[author] = author_stat
        except:
            print(json.dumps(_json_res, indent=4))

    return [
        {
            "github_id": author,
            "commit_count": commit_count[author],
            "stats": commit_stat[author],
        }
        for author in commit_stat.keys()
    ][0]


def extract_diff(head, base):
    cmd = f"git diff {base}..{head}"
    res = subprocess.run(cmd, capture_output=True, shell=True)
    return res.stdout.decode()


def post_request(pr_url, endpoint, contributors, reviewers, summary):

    body = {
        "pr_url": pr_url,
        "author_id": contributors["github_id"],
        "commit_count": contributors["commit_count"],
        "additions": contributors["stats"]["additions"],
        "deletions": contributors["stats"]["deletions"],
        "total": contributors["stats"]["total"],
        "summary": summary,
        "reviewer_id": reviewers,
    }
    print(json.dumps(body, indent=4))
    res = requests.post(f"{endpoint}/pr", json=body)
    print(json.dumps(res.json(), indent=4))

    if res.status_code != 200:
        exit(1)


def to_flex_message(summary):
    summary = summary.replace("'", "\\'")
    res = subprocess.run(f"node get_flex_message.js '{summary}'", capture_output=True, shell=True)
    return res.stdout.decode()


def main():
    token, repo, pr_num, endpoint, genmini_api_key = sys.argv[1:6]

    pr_url, diff, reviewers = get_diff_and_reviewers(token, repo, pr_num)
    summary = get_review_summary(diff, genmini_api_key)
    flex_message = to_flex_message(summary)
    contributors = get_contributors(token, repo, pr_num)
    post_request(pr_url, endpoint, contributors, reviewers, flex_message)


if __name__ == "__main__":
    main()
