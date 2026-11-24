"""#3158 Dockerfile 与 .dockerignore 静态核验（本机无 docker，不构建镜像）。

核验点：
- 后端 Dockerfile：多阶段、python:3.11-slim、非 root 用户 app、8000、
  HEALTHCHECK 探活 /healthz、uvicorn 启动且关默认访问日志、不 COPY .env。
- 前端 Dockerfile：Node 构建 + nginx:alpine、非 root 用户 nginx、8080、
  HEALTHCHECK 探活 /healthz、nginx.conf 含 gzip 与 SPA 回退。
- .dockerignore：对仿真构建上下文逐文件判定，.env*、.git、tests/fixtures、
  node_modules 一律排除，源码与配置保留。
- 基础镜像 tag 与 2026-11-24 经 Docker Hub API 核验过的 pin 一致。
"""

import fnmatch
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

PINNED_BASES = {"python:3.11-slim", "node:22-alpine", "nginx:1.30-alpine"}


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def from_lines(text: str) -> list[str]:
    return [
        line.split(" AS ")[0].split(" as ")[0].strip()
        for line in text.splitlines()
        if line.strip().upper().startswith("FROM ")
    ]


# ---------------- 后端 Dockerfile ----------------


def test_backend_setuptools_removed_after_copy_not_before():
    # 第七轮 P0-3（合并版）：删除 setuptools/wheel 必须放在 COPY 之后——
    # COPY 之前删，builder 装进 /install 的 setuptools 还会被 COPY 回来。
    # builder 保留升级下限（setuptools>=82.0.0 / wheel>=0.46.2），
    # runtime 在 COPY 之后删干净并用 find_spec 自证。
    dockerfile = read("app/Dockerfile")
    copy_pos = dockerfile.index("COPY --from=builder /install /usr/local")
    rm_pos = dockerfile.index("rm -rf /usr/local/lib/python3.11/site-packages/setuptools")
    assert rm_pos > copy_pos, "删除 setuptools 必须放在 COPY 之后"
    assert "setuptools>=82.0.0" in dockerfile and "wheel>=0.46.2" in dockerfile, \
        "builder 升级下限 setuptools>=82.0.0 / wheel>=0.46.2 须保留"
    assert "--prefix=/tools" not in dockerfile, \
        "合并版不走 /tools 隔离（COPY 后删已由 161 实测通过），不留死代码"
    # COPY 之前的 groupadd 段里不许再有 rm（旧版的 pre-COPY 删法已作废）
    assert "rm -rf" not in dockerfile[:copy_pos], "COPY 之前不许删 setuptools"


def test_backend_runtime_has_no_setuptools_wheel():
    # 第七轮 P1-2（合并版）：最终镜像里确实没有 setuptools / wheel——
    # 用 find_spec 自证（比只看路径更强：import 不到才算真的不在），
    # 且自证必须在 COPY 之后（COPY 之前 fastapi 还没装进来）。
    dockerfile = read("app/Dockerfile")
    copy_pos = dockerfile.index("COPY --from=builder /install /usr/local")
    check_pos = dockerfile.index("find_spec('setuptools')")
    assert check_pos > copy_pos, "无 setuptools 自证必须在 COPY 之后"
    assert "find_spec('wheel') is None" in dockerfile, "须同时断言 wheel 不在镜像里"
    assert "find_spec('setuptools') is None" in dockerfile, "须断言 setuptools 不在镜像里"


def test_backend_multistage_and_pinned_base():
    text = read("app/Dockerfile")
    froms = from_lines(text)
    assert len(froms) == 2, f"后端须恰好两阶段，实测 {froms}"
    assert all(f == "FROM python:3.11-slim" for f in froms)


def test_backend_non_root_user():
    text = read("app/Dockerfile")
    assert "useradd -r -u 10001 -g app app" in text
    assert re.search(r"^USER app$", text, re.M)


def test_backend_port_healthcheck_cmd():
    text = read("app/Dockerfile")
    assert "EXPOSE 8000" in text
    assert "HEALTHCHECK" in text and "/healthz" in text
    assert 'CMD ["uvicorn", "main:app"' in text
    assert "--no-access-log" in text, "须关 uvicorn 默认访问日志（#3190 统一输出）"


def test_backend_does_not_copy_env():
    text = read("app/Dockerfile")
    for line in text.splitlines():
        if line.strip().upper().startswith(("COPY", "ADD")):
            assert ".env" not in line, f"Dockerfile 不得 COPY .env：{line}"


def test_backend_builder_prefix_matches_copy():
    text = read("app/Dockerfile")
    assert "pip install --no-cache-dir --prefix=/install" in text
    assert "COPY --from=builder /install /usr/local" in text


# ---------------- 前端 Dockerfile 与 nginx ----------------


def test_web_multistage_and_pinned_base():
    text = read("web/Dockerfile")
    froms = from_lines(text)
    assert froms == ["FROM node:22-alpine", "FROM nginx:1.30-alpine"]


def test_web_non_root_and_port():
    text = read("web/Dockerfile")
    assert re.search(r"^USER nginx$", text, re.M)
    assert "EXPOSE 8080" in text, "非 root 绑不了 80，改听 8080（部署层映射）"
    assert "HEALTHCHECK" in text and "8080/healthz" in text
    assert "npm ci" in text and "npm run build" in text
    assert "COPY web/nginx.conf /etc/nginx/conf.d/default.conf" in text


def test_nginx_gzip_spa_fallback_healthz():
    text = read("web/nginx.conf")
    assert "listen       8080;" in text
    assert "gzip on;" in text
    assert "application/javascript" in text
    assert "try_files $uri $uri/ /index.html;" in text
    assert "location = /healthz" in text


# ---------------- 基础镜像 pin ----------------


def test_all_base_images_pinned_to_verified_tags():
    bases = set()
    for rel in ("app/Dockerfile", "web/Dockerfile"):
        for line in read(rel).splitlines():
            if line.strip().upper().startswith("FROM "):
                bases.add(line.split()[1])
    assert bases == PINNED_BASES, f"基础镜像须与核验过的 pin 一致，实测 {bases}"


# ---------------- .dockerignore 仿真 ----------------
#
# 简化版 docker 忽略规则：无 `/` 的模式按 basename 全层匹配；
# 含 `/` 的模式锚定上下文根；目录模式排除其下全部文件；
# `*` 不跨 `/`，`**` 跨 `/`。与 docker 行为一致的部分已足够判定验收 2。


def _pattern_to_regex(pattern: str) -> re.Pattern:
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if pattern[i : i + 2] == "**":
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def _load_ignore_patterns() -> list[str]:
    patterns = []
    for line in read(".dockerignore").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def _ignored(path: str, patterns: list[str]) -> bool:
    ignored = False
    for pat in patterns:
        negated = pat.startswith("!")
        p = pat[1:] if negated else pat
        hit = False
        if "/" not in p.rstrip("/"):
            # 无斜杠的模式按任一路径段匹配；段是目录时排除其下全部文件
            rx = _pattern_to_regex(p.rstrip("/"))
            segments = path.split("/")
            if any(rx.match(seg) for seg in segments):
                hit = True
            for i in range(1, len(segments)):
                if rx.match("/".join(segments[:i])):
                    hit = True
        else:
            rx = _pattern_to_regex(p.rstrip("/"))
            if rx.match(path):
                hit = True
            elif re.match(r"^" + rx.pattern[1:-1] + r"/.*$", path):
                hit = True
        if hit:
            ignored = not negated
    return ignored


@pytest.fixture()
def fake_context(tmp_path: Path) -> Path:
    files = {
        ".env": "FAKE_SECRET=do-not-use\n",
        ".env.local": "FAKE_SECRET=do-not-use\n",
        ".git/HEAD": "ref: refs/heads/main\n",
        "tests/fixtures/sample.json": '{"sample": true}\n',
        "node_modules/pkg/index.js": "module.exports = {};\n",
        "app/main.py": "x = 1\n",
        "app/requirements.txt": "fastapi==0.165.0\n",
        "web/Dockerfile": "# web dockerfile\n",
        "web/nginx.conf": "server {}\n",
        "README.md": "# readme\n",
        ".venv/lib/x.py": "x = 1\n",
        "src/__pycache__/x.pyc": "x",
    }
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp_path


def test_dockerignore_excludes_secrets_git_fixtures_modules(fake_context: Path):
    patterns = _load_ignore_patterns()
    assert patterns, ".dockerignore 不得为空"
    excluded = {
        ".env",
        ".env.local",
        ".git/HEAD",
        "tests/fixtures/sample.json",
        "node_modules/pkg/index.js",
        ".venv/lib/x.py",
        "src/__pycache__/x.pyc",
    }
    kept = {
        "app/main.py",
        "app/requirements.txt",
        "web/Dockerfile",
        "web/nginx.conf",
        "README.md",
    }
    all_files = {
        str(p.relative_to(fake_context))
        for p in fake_context.rglob("*")
        if p.is_file()
    }
    assert all_files == excluded | kept
    for rel in sorted(excluded):
        assert _ignored(rel, patterns), f"应被排除却保留：{rel}"
    for rel in sorted(kept):
        assert not _ignored(rel, patterns), f"应保留却被排除：{rel}"


def test_dockerignore_covers_scope_items():
    text = read(".dockerignore")
    for item in (".env*", ".git", "tests/fixtures", "node_modules"):
        assert item in text, f".dockerignore 缺少范围要求的排除项：{item}"
