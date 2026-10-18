---
id: 0078
scope: meta
status: 承認済み
date: 2026-10-18
approved_by: "人間指示（2026-10-18 チャット、Linear KEN-56）: 混ぜて回すときはSonnetとLuna、Lunaは最新世代、単独runtimeでは使い分けを残す、Claude単独は現状維持、指揮役はOpus。ADR-0075により運用表の更新はAIが自律して起票してよい"
supersedes: []
superseded_by: null
relates_to: [0004, 0036, 0048, 0068, 0075]
---

# ADR-0078: Codexのモデルは階級で固定して世代は最新を使い、指揮役はOpusにする

> **承認者向けサマリ**: 2点を決める。(1) Codexのモデルを「階級（luna / terra / sol）を固定し、世代はその階級の
> 最新」で指定する。(2) Orcaで回す指揮役を、精度が悪かったためSonnetからOpusに変える。
> 結果、混ぜて回す基本構成はorchestrator=Claude Opus、architect・reviewer=Claude Sonnet、designer=Claude Opus、
> developer・tester=Codex `gpt-6-luna`。Codexだけで回すときはarchitect・reviewer=`gpt-5.6-terra`、
> designer=`gpt-6.1-sol`、developer・tester=`gpt-6-luna`（階級の割り当ては0048のまま）。Claudeだけは変更なし。

## 文脈

`meta/agent-runtime-mapping.md` はCodexのモデルを `gpt-5.6-*` の固定名で持っていたが、Codexのモデル一覧
（`~/.codex/models_cache.json`、2026-10-11）には `gpt-6.1-sol`、`gpt-6-astra`、`gpt-6-sol`、`gpt-6-luna` があり、
`gpt-5.6-*` は「Older generation」と注記されている。ADR-0068は指揮役をSonnetとしたが、運用してみて精度が悪い
との指摘が人間からあった。

## 決定

1. 割り当ての本体は階級とし、世代はその階級の最新を使う。階級に最新世代が無いときは、その階級の最新を使い、階級を変えない（terraは5.6が最新）。
2. 世代の更新は表・既定の実行先・`orchestration.md` の例を同じPRで更新する。階級を変えるときだけADRを起こす。
3. 指揮役（orchestrator）はClaude Opusとする。Orca側のClaude既定モデルをOpusにする（人間の作業）。ADR-0068の指揮役の記述（Sonnet）はこの決定で置き換える。
4. 利用不能なときに別モデルへ黙って代替しない規定は維持する。

## 結果

- 混ぜて回すとき: orchestrator=Claude Opus、architect・reviewer=Claude Sonnet、designer=Claude Opus、developer・tester=`gpt-6-luna`。
- Codexだけのとき: architect・reviewer=`gpt-5.6-terra`、designer=`gpt-6.1-sol`、developer・tester=`gpt-6-luna`。
- Claudeだけのときは `sonnet` / `opus` の別名のまま変更なし。
- 未確認: Orca経由の `--model gpt-6-luna` 起動の実動作。最初のdispatchで確かめる。Orca側の既定モデルのOpus化も人間の作業として残る。
