#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

python_bin="${PYTHON:-$project_dir/.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then
    echo "Activate the project environment and set PYTHON to its Python executable." >&2
    exit 1
fi

"$python_bin" -m paperleet.cli export
npm --prefix web run build
npm --prefix web run check:build

mkdir -p reports/deploy
COPYFILE_DISABLE=1 tar --no-xattrs -czf reports/deploy/paperleet-coding-site.tar.gz -C web/dist .
echo "Static release: $project_dir/reports/deploy/paperleet-coding-site.tar.gz"
echo "Nginx template: $project_dir/deploy/aliyun/nginx.conf"
