---
id: 0021
scope: project/toyama-dining-radar
status: 承認済み
date: 2026-08-11
approved_by: "PR #90 のマージをもって承認（ADR-0035方式(i)。本ADR本文が自ら宣言した方式である）。
  人間裁定 2026-08-11 chat: 最初の公開先をRenderとし、無料で維持できる構成を採る。マージ時点で
  Render/Neonのresourceは未作成であり、本承認は構成の選択を確定するものであって、外部accountの
  変更とsecret投入の実施を承認するものではない（DEPLOYMENT.md の事前条件を参照）。"
supersedes: []
superseded_by: null
relates_to: [P-01, P-02, P-04, P-05, P-08, P-10, ADR-0002, ADR-0006, ADR-0007, ADR-0008, ADR-0010, ADR-0018]
---

# ADR-0021: 無料Render Webと無料Neon Postgresで最初の公開構成を作る

> **承認者向けサマリ**: 人間は2026-08-11のchatで、最初の公開先をRenderとし、
> 無料で維持できる構成を採用する方向を確認した。本ADRは無料Render Web、無料Neon
> Postgres、WhiteNoise、単一Gunicorn workerを最初の公開構成とする。実在の公開host、
> DB接続情報、API key、検索地点、初回account情報はruntime secretだけに置く。
> 本ADRはPRのマージをもって承認とする（ADR-0035方式(i)）。

## 文脈

このアプリはDjango sessionと管理者作成accountをDBへ保存する一方、providerの店舗情報、
検索履歴、検索地点は永続化しない。現在のSQLiteはRenderの揮発filesystemではdeploy、restart、
idle後の再起動で失われる。Render無料Postgresは30日で失効するため継続運用に使えない。
無料Webは15分のidle後に停止し、次のrequestでcold startするが、5人程度の断続的な利用では
このUX上の制約を費用ゼロとの交換条件として受け入れられる。

また、OSM標準tileの現行policyはweb pageから正しいRefererを送ることを要求する。
`SECURE_REFERRER_POLICY = "same-origin"` はcross-origin tile requestからRefererを除去するため、
公開originだけを送る `strict-origin-when-cross-origin` へ合わせる必要がある。検索地点はURLにも
browserにも存在しないため、この変更で非公開地点を送信しない。

## 決定

1. Render Singaporeの無料Web Serviceを1 instance、Gunicorn 1 workerで動かす。idle cold startを
   許容し、keep-alive目的の自動pingは導入しない。
2. account、password hash、Django session、migration stateはNeon Singaporeの無料Postgresへ
   TLS必須で保存する。provider response、候補、検索履歴、検索地点は保存しない。
3. Renderのfilesystemはbuild artifact以外の永続化に使わない。static assetはbuild時に
   `collectstatic`し、WhiteNoiseから同一origin配信する。persistent diskは付けない。
4. Renderが終端したHTTPSは、Render環境でのみ`X-Forwarded-Proto`を信頼してDjangoへ伝える。
   Secure/HttpOnly/SameSite cookie、CSRF、HTTPS redirect、HSTS、host allowlistを維持する。
5. health checkはDBへの`SELECT 1`だけを行う。providerを呼ばず、設定値や例外を応答へ出さない。
6. 無料Webにはoperator shellがないため、初回organizerはwrite-only runtime secretからbuild時に
   1回作る。同名accountが存在する場合はpasswordや権限を変更しない。login確認後、bootstrap
   secretはRenderから削除する。
7. `Referrer-Policy`は`strict-origin-when-cross-origin`とし、OSMへ公開originだけを送る。
   Leaflet本体のsame-origin vendoringと表示中tileだけを取得する境界は変更しない。

## 却下した案

- **Render無料Postgres**: 30日で失効し、accountとsessionを継続できない。
- **Render上のSQLite**: filesystem消失でaccountが失われる。
- **有料Render Web/Postgres**: cold startと運用制約は減るが、現段階の利用規模に対して費用を
  先行させるため採用しない。利用増加時の移行先として残す。
- **Koyeb無料Web**: cold startは短いが無料regionが日本から遠く、今回の人間選択はRenderである。
- **Cloud Run**: 無料枠はあるがbilling accountとcontainer運用を追加し、最初の公開には複雑すぎる。

## 帰結

- 無料枠はSLA、常時起動、backupを保証しない。昼の最初の利用者にはcold startを説明する。
- NeonまたはRenderの無料条件が変わった場合は、費用発生前に停止し、paid化または移転を再判断する。
- 実public HTTPS、redirect、cookie、OSM Referer、provider creditはdeploy後のL5で確認する。
- 実リソース作成とsecret投入は外部状態変更であり、コードのマージとは別に人間確認を要する。
