# dining-radar

幹事が昼の会を立て、参加者が日程と店を答え、幹事が決めるところまでを扱う Web アプリ。
本体は [projects/dining-radar/](projects/dining-radar/) にある。

このリポジトリは [ai-driven-dev-template](https://github.com/Vazial/ai-driven-dev-template) から
2026-09-26 に切り出した（テンプレ側の `meta/adr/0067`）。進め方の規程（`meta/`・`.claude/agents/` ほか）は
テンプレの写しであり、どのコミットから写したかを [TEMPLATE_SYNC](TEMPLATE_SYNC) が記録している。

- テンプレの更新を取り込む: `scripts/template-pull.sh`（作業ブランチで走らせ、結果をPRにする）
- 写しを直接いじっていないか確かめる: `scripts/template-pull.sh --check`
- 規程そのものを直したいときは、テンプレ側に PR を出し、通ってから取り込む

作業を始めるときは [HANDOFF.md](HANDOFF.md) から読む。
