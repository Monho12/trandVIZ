#!/usr/bin/env bash
# Hugging Face Space руу байршуулах (#9, ADR 0008).
#
#   bash scripts/deploy_space.sh          # HEAD-ийг `space` remote руу
#   bash scripts/deploy_space.sh <commit> # өөр commit-ийг
#
# Яагаад энгийн `git push space main` биш вэ: HF нь 10 MB-аас том эсвэл binary файлыг
# (app/model/*.cbm 20–25 MB, *.parquet, *.woff2) LFS/Xet-гүй push хийхийг хориглодог,
# харин GitHub-ийн түүхэд эдгээр нь энгийн blob. Тиймээс скрипт тухайн commit-ийн
# НЭГ commit-тэй хуулбарыг түр хавтсанд хийж, binary/том файлыг LFS-ээр track хийгээд
# Space руу --force push хийнэ. GitHub-ийн repo, түүх огт өөрчлөгдөхгүй.
#
# Урьдчилж (Майк өөрөө, docs/PLAN.md -> "Hugging Face тохиргоо"):
#   huggingface-cli login            # "Add token as git credential?" -> Y
#   git remote add space https://huggingface.co/spaces/<нэр>/shuugian
# Token-ийг энэ скрипт, repo, чат хаана ч бичихгүй: git credential helper-ээс авна.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
ref="${1:-HEAD}"
sha="$(git rev-parse --short "$ref")"

url="${SPACE_URL:-$(git remote get-url space 2>/dev/null || true)}"
if [[ -z "$url" ]]; then
  echo "space remote алга. Эхлээд: git remote add space https://huggingface.co/spaces/<нэр>/shuugian" >&2
  exit 1
fi
command -v git-lfs >/dev/null || { echo "git-lfs суулгана уу: https://git-lfs.com" >&2; exit 1; }
if [[ "$ref" == HEAD && -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "Анхаар: commit хийгээгүй өөрчлөлт Space руу ОРОХГҮЙ (зөвхөн $sha)." >&2
fi
commit_name="$(git config user.name || echo 'shuugian deploy')"
commit_email="$(git config user.email || echo 'deploy@localhost')"

# macOS-ийн bash 3.2 + BSD find дээр ч ажиллахаар бичсэн (mapfile, find -printf ашиглахгүй)
tmp="$(mktemp -d)"
lfs_list="$(mktemp)"
trap 'rm -rf "$tmp" "$lfs_list"' EXIT
git archive "$ref" | tar -x -C "$tmp"

cd "$tmp"
git init -q -b main
git lfs install --local >/dev/null
git add -A
# binary (numstat нь "-") эсвэл ~10 MB хүрэх (HF-ийн хязгаар 10 MB, 9M-ээр нөөцтэй) файл бүрийг LFS-ээр
empty_tree="$(git hash-object -t tree /dev/null)"
git -c core.quotePath=false diff --cached --numstat "$empty_tree" | awk -F'\t' '$1 == "-" { print $3 }' > "$lfs_list"
find . -type f -size +9M ! -path './.git/*' | sed 's#^\./##' >> "$lfs_list"
sort -u -o "$lfs_list" "$lfs_list"
n_lfs="$(wc -l < "$lfs_list" | tr -d ' ')"
if [[ "$n_lfs" -gt 0 ]]; then
  while IFS= read -r f; do git lfs track --filename "$f" >/dev/null; done < "$lfs_list"
  git add --renormalize .   # шинэ .gitattributes-ээр дахин stage: LFS pointer болно
  git add .gitattributes
fi
git -c user.name="$commit_name" -c user.email="$commit_email" commit -q -m "Deploy $sha (github.com/Monho12/trandVIZ)"
echo "LFS: $n_lfs файл. Push: $sha -> space main"
git push -q --force "$url" main
echo "Болсон. Space build-ийг Space-ийн 'Logs' tab-аас харна уу."
