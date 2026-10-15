---
id: 0082
scope: project/dining-radar
status: 提案中
date: 2026-10-15
approved_by: null
supersedes: []
superseded_by: null
relates_to: [ADR-0039, ADR-0041, ADR-0057]
---

# ADR-0082: PRではPythonソース差分だけを変異テストし、全体検査をmain後と夜間に行う

> **承認者向けサマリ**: PythonのミューテーションテストがPRのL1実行時間を大きく占め、画面や文書だけのPRにも同じ全体検査が走る。PRでは変更されたPythonソースに対応する変異だけを検査し、Pythonソースに変更がなければ変異テストを省略する。mainへのマージ後と夜間scheduleでは全体を検査し、既存の閾値は変えない。失敗はGitHub Actionsのworkflow失敗通知で知らせる。

## 1. 文脈

現在の `ci-dining-radar.yml` は、PRのL1 jobでアプリケーション全体のPythonミューテーションを実行する。そのため、差分が小さい実装PRでも全体の変異を待ち、画面・文書だけのPRでも同じ検査が起動する。一方、全体の検査を失うと、変更されていないコードの検出力を定期的に確認できなくなる。

この変更で、PR時のL1保証の置き場所が「全体コードの全変異を毎回検査」から「変更されたPythonソースの変異をPRで検査」へ移る。全体コードに対する保証は、mainへのマージ後と夜間scheduleに置く。したがってPRの緑だけでは、変更されていないPythonソース全体の現在のミューテーションスコアを保証しない。全体保証はmain後・夜間のworkflow結果で確認する。

## 2. 決定

1. `pull_request` では、PRのbase SHAとの差分に含まれる `projects/dining-radar/src/**/*.py` がある場合だけ、pytest-gremlinsに `--diff <base SHA>` を渡して変更部分の変異を実行する。
2. Pythonソース差分がないPRでは、Pythonミューテーションのstepを実行しない。通常のruff・単体テスト・カバレッジは従来どおり実行する。
3. `main`へのpush（マージ後）と毎夜のscheduleでは、Pythonと既存のclient JSの全体ミューテーションを実行する。PRではclient JSの全体ミューテーションも実行せず、PRのミューテーションは変更Pythonソースの差分だけに限定する。
4. ミューテーションスコアの閾値（Python 80%、client JSの既存閾値）と既存の判定は変更しない。
5. ミューテーションが失敗した場合は、GitHub Actionsのworkflow失敗として扱う。GitHubのActions画面で失敗を確認でき、対象workflowを購読している利用者にはGitHub標準の失敗通知が届く。外部通知サービス・Webhook秘密情報・追加の通知基盤は導入しない。

## 3. この通知方式を選んだ理由

GitHub Actionsの標準通知は、PRとmain後・scheduleの両方を同じworkflow結果として扱え、通知先の管理をリポジトリ外へ持ち出さない。外部Webhook方式は、秘密情報の管理、送信先の変更、夜間実行時の失敗経路を追加するため、このプロジェクトのCI運用に対して重い。workflow失敗を通知の一次記録にすることで、失敗ログと通知が同じ実行に結びつく。

## 4. 検討した代替案

- **PRごとに全体ミューテーションを続ける**: 全体保証は強いが、変更のないPRにも長い待ち時間を要求し、今回の運用上のボトルネックを解消しないため採用しない。
- **client JSの全体ミューテーションだけPRに残す**: Python差分だけのPRでも長時間のJS全体検査が残り、画面・文書だけのPRでミューテーションを省くという運用にならないため採用しない。
- **外部Webhook（Slack等）へ送る**: 通知到達性を高められる可能性はあるが、秘密情報・送信先・外部障害をCIへ追加するため採用しない。
- **PRではミューテーションを完全に省略し、定期実行だけにする**: 高速だが、変更されたPythonソースへの即時の変異保証を失うため採用しない。

## 5. 影響と検証

- L1の保証位置が変わるため、本ADRはプロジェクトscopeの制約ADRとして人間承認を要する。
- L1のPython全体ミューテーション所要時間は、実装PR本文に実測値を記載する。client JS全体ミューテーションはPRでは実行せず、main後・夜間の結果で確認する。
- ワークフロー構文はactionlint等で検証し、`.github/workflows/ci-dining-radar.yml` 以外の既存workflowは変更しない。
- PR提出前にリポジトリ全体で `ruff check .` と `ruff format --check .` を実行する。
