#!/usr/bin/env bash
# Publica os dados coletados, lidando com o push concorrente do outro workflow.
set -u
cd "$(dirname "$0")/.."

git add docs/dados/brasil.json docs/dados/brasil_historico.jsonl 2>/dev/null
git diff --staged --quiet && exit 0

git commit -q -m "brasil: apuração $(date -u '+%Y-%m-%d %H:%M UTC')"

for tentativa in 1 2 3; do
  git push -q origin main 2>/dev/null && exit 0
  git fetch -q origin main
  if ! git rebase -q origin/main 2>/dev/null; then
    # brasil.json é regenerado a cada leitura: a versão local é a mais nova.
    # Os .jsonl têm merge=union e se resolvem sozinhos.
    git checkout --theirs docs/dados/brasil.json 2>/dev/null
    git add docs/dados/ 2>/dev/null
    GIT_EDITOR=true git rebase --continue >/dev/null 2>&1 || git rebase --abort
  fi
done
echo "aviso: não consegui publicar após 3 tentativas" >&2
