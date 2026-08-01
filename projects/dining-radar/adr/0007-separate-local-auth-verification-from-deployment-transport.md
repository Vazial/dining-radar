---
id: 0007
scope: project/toyama-dining-radar
status: 承認済み
date: 2026-08-01
approved_by: "人間裁定 2026-08-01（TDR-AUTH-01〜05・07 はローカル browser L4、TDR-AUTH-06 はローカル L3 設定検証、実 HTTPS transport は deployment slice へ送る）"
supersedes: []
superseded_by: null
relates_to: [P-01, P-02, P-03, P-04, P-10, TDR-AUTH-01, TDR-AUTH-02, TDR-AUTH-03, TDR-AUTH-04, TDR-AUTH-05, TDR-AUTH-06, TDR-AUTH-07]
---

# ADR-0007: ローカル認証の受け入れ検証と公開 transport の検証を分離する

> **承認者向けサマリ**: ローカルで認証の主要な利用者体験を browser L4 で確認し、公開時に必須の cookie・CSRF・CORS・token 非使用は設定/境界の L3 で確認する。実際の HTTPS 接続、証明書、公開 origin はデプロイを決めるスライスまで検証しない。これにより、デプロイを先取りせずに認証実装を検証できる。

## 文脈

ADR-0006 と TDR-AUTH-06 は、将来インターネットへ公開する browser session に HTTPS、Secure/HttpOnly/SameSite cookie、CSRF、same-origin を要求する。一方、この実装スライスは host、domain、certificate、デプロイ provider を選ばず、実 HTTPS transport を提供しない。ローカル HTTP で Secure cookie を browser session に使わせることもできない。

人間裁定は、ローカル slice の browser L4 を TDR-AUTH-01〜05・07 に限定し、TDR-AUTH-06 の設定・安全境界を L3 で確認すること、そして actual HTTPS transport の検証を deployment slice へ送ることだった。最初の test-support seam 契約は Given 状態だけを定め、browser が操作・観測する control surface と、この検証分離を機械可読にしていなかった。

## 決定

1. ローカル acceptance browser は、TDR-AUTH-01〜05・07 を `contracts/authentication-browser-interface.yaml` の control surface と観測だけで実行する。候補探索の未認証 API 応答は既存の `contracts/candidate-search-api.yaml` をそのまま使う。
2. TDR-AUTH-06 は local L3 で確認する。deployment 向け設定は HTTPS、`Secure`/`HttpOnly`/`SameSite` cookie、CSRF、credential を伴う任意 origin CORS 非許可、browser local-storage bearer token 不使用を要求する。ローカル acceptance profile だけは browser session を成立させるため session cookie の `Secure` 属性を緩和できるが、これは公開構成へ持ち込めない限定例外である。`HttpOnly`、`SameSite`、CSRF、same-origin の要求はローカルでも維持する。
3. 実 HTTPS handshake、HTTP から HTTPS への遷移、証明書、実 public origin、実 CORS allowlist の確認は deployment slice の L3/L5 に送る。ローカルの HTTP 実行を公開 transport の合格証明として扱わない。
4. `contracts/test-support-api.yaml` は acceptance-only の security-boundary observation を持つ。これは実行中の acceptance profile が有効にしている境界を機械検証するための seam であり、browser-facing API でも公開 deployment の設定値でもない。

## 検討した代替案

- **ローカルでも HTTPS を必須にする**: 証明書・origin・運用を認証実装より先に選ぶことになり、deferred deployment scope を破るため採用しない。
- **TDR-AUTH-06 をローカルでは検証しない**: Secure cookie、CSRF、CORS、token 非使用の回帰を deployment まで見逃すため採用しない。
- **browser test を捨て、全認証を設定/HTTP unit test だけで済ませる**: login/logout/password change/disabled account の control surface を検証できないため採用しない。

## 帰結

- 実装と tester は browser control surface、local/deployment profile、security observation の原本として `contracts/authentication-browser-interface.yaml` と `contracts/test-support-api.yaml` を参照する。プロンプト上の言い換えはしない。
- TDR-AUTH-06 の受け入れ文言と ADR-0006 の公開時要求は変更しない。変わるのは、この slice での検証層と実 HTTPS の検証時期だけである。
- deployment slice は real origin を公開リポジトリへ記録せず、actual HTTPS transport と local exception の不在を検証する責務を持つ。
