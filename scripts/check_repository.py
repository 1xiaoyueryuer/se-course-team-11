"""Check lightweight repository conventions with Python's standard library."""

import argparse
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
TITLE = re.compile(r"^(前端|后端|知识库|测试|文档|工程)：\s*(\S.*)$")
TRIVIAL = {"更新", "修改", "修复", "调整", "完善", "更新文档", "修改一下", "修复一些问题"}
MEMBER_BRANCHES = {"member/a", "member/b", "member/c", "member/d"}
REPOSITORY = "1xiaoyueryuer/se-course-team-11"


def branch_errors(branch, *, pull_request=False, head_repository=None):
    allowed = MEMBER_BRANCHES if pull_request else MEMBER_BRANCHES | {"main"}
    errors = []
    if branch not in allowed:
        errors.append(f"分支 {branch!r} 不符合固定个人分支约定")
    if pull_request and head_repository != REPOSITORY:
        errors.append("团队 PR 必须来自本仓库已分配的固定成员分支")
    return errors


def title_error(title):
    match = TITLE.fullmatch(title.strip())
    if not match:
        return "标题须为 类别：具体中文行为，类别为前端/后端/知识库/测试/文档/工程"
    body = match.group(2).strip()
    if not re.search(r"[\u4e00-\u9fff]", body) or body in TRIVIAL or len(body) < 4:
        return "冒号后须用中文说明具体交付结果，不能只写更新/修改等空话"
    return None


def git(*args):
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, encoding="utf-8", check=True
    )
    return result.stdout


def file_errors(paths):
    errors = []
    required = {"AGENTS.md", "README.md", "CONTRIBUTING.md"}
    errors.extend(f"缺少入口文件：{name}" for name in sorted(required - set(paths)))
    feature_files = {}
    for name in paths:
        path = PurePosixPath(name)
        if path.suffix.lower() == ".md":
            if len(path.parts) == 1 and name not in required:
                errors.append(f"根目录不新增散落 Markdown：{name}")
            if path.name.lower() in {"agent.md", "agents.md"} and name != "AGENTS.md":
                errors.append(f"智能体规则统一使用根目录 AGENTS.md：{name}")
        if path.parts[:2] == ("docs", "features"):
            if len(path.parts) != 4:
                errors.append(f"功能目录只放对应两份方案：{name}")
                continue
            folder = path.parts[2]
            match = re.fullmatch(r"F[0-9]{2,}-(.+)", folder)
            if not match:
                errors.append(f"功能目录须为 F01-功能名称：{name}")
                continue
            feature = match.group(1)
            expected = {f"{feature}功能架构方案.md", f"{feature}功能代码实施方案.md"}
            if path.name not in expected:
                errors.append(f"功能文档命名不符或存在额外文件：{name}")
            feature_files.setdefault(folder, set()).add(path.name)
    for folder, actual in feature_files.items():
        feature = folder.split("-", 1)[1]
        expected = {f"{feature}功能架构方案.md", f"{feature}功能代码实施方案.md"}
        for missing in sorted(expected - actual):
            errors.append(f"功能方案不成对：docs/features/{folder}/{missing}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="PR base commit; checks every commit in base..head")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--check-head", action="store_true", help="Check the current commit title")
    parser.add_argument("--branch", help="Explicit branch for detached CI checkouts")
    args = parser.parse_args()
    try:
        # Include untracked nonignored files for useful local precommit checks.
        paths = set(git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0"))
        paths.discard("")
        # A staged deletion should not be treated as a present local document.
        paths = {name for name in paths if (ROOT / name).is_file()}
        errors = file_errors(paths)
        pr_branch = os.environ.get("PR_HEAD_BRANCH")
        branch = pr_branch if pr_branch is not None else (args.branch or git("branch", "--show-current").strip())
        errors.extend(branch_errors(
            branch, pull_request=pr_branch is not None,
            head_repository=os.environ.get("PR_HEAD_REPOSITORY"),
        ))
        titles = []
        if args.base:
            if not re.fullmatch(r"[a-fA-F0-9]{40}", args.base):
                raise ValueError("--base 必须是完整提交 SHA")
            if not re.fullmatch(r"[a-fA-F0-9]{40}|HEAD", args.head):
                raise ValueError("--head 必须是完整提交 SHA 或 HEAD")
            titles = git("log", "--format=%s", f"{args.base}..{args.head}").splitlines()
        elif args.check_head:
            titles = [git("log", "-1", "--format=%s").strip()]
        for title in titles:
            problem = title_error(title)
            if problem:
                errors.append(f"提交标题 {title!r}：{problem}")
        pr_title = os.environ.get("PR_TITLE")
        if pr_title is not None:
            problem = title_error(pr_title)
            if problem:
                errors.append(f"PR 标题：{problem}")
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(f"检查无法完成：{exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 1
    print("固定分支、文档位置、功能方案配对及指定范围标题检查通过。")
    print("此检查不判断成员写权限、修改范围授权、功能完整性或人工审核状态。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
