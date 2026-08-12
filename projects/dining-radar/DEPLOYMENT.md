# 無料公開環境の構築手順

この手順は [ADR-0021](adr/0021-adopt-free-render-neon-deployment-topology.md) の
Render Free Web + Neon Free PostgreSQL 構成を対象とする。外部resourceの作成とsecret投入は
人間の明示確認後に行う。secretや検索地点の実値は、この文書、issue、PR、build logへ書かない。

## 事前条件

- GitHub上の公開対象branchへ、承認済みPRがmerge済みであること。
- RenderとNeonのaccountを人間が管理できること。
- 無料Render Webはidle時に停止してcold startする。常時応答やSLAが必要になったら有料化または
  移転を再判断する。
- 無料枠の上限・保存期間・利用条件は変更され得るため、作成前に
  [Render Free](https://render.com/docs/free) と [Neon plans](https://neon.com/pricing) を再確認する。

### 再確認済みの無料枠（2026-08-12時点）

作成前の再確認は毎回必要である。以下は最後に確認した時点の値であり、差分を見るための基準として
だけ使う。

| | Render Free Web | Neon Free |
|---|---|---|
| 停止条件 | inbound trafficが**15分**無いとspin down（復帰に約1分） | **5分**idleでscale to zero（Freeでは常時有効） |
| 月次上限 | workspaceあたり**750 instance時間** | projectあたり**100 CU時間** / **0.5 GB** |
| 保存 | filesystemはephemeral・persistent disk不可・SSH不可 | branch 10本 / instant restore 6時間 |
| 期限 | — | 期限なし（trialではない） |

Renderの無料PostgreSQLは**作成から30日で失効**するため採用しない。DBはNeonに置く。これがADR-0021が
2つのproviderに分ける理由である。

**health checkの挙動**（`/healthz`の設計がこれに依存する）: Renderのhealth checkは**edgeを経由せず
サービスのportへ直接**届くため `X-Forwarded-Proto` が付かない。`Host` はサービスの `onrender.com`
subdomain（verified custom domainがあればそちら）。**`2xx`または`3xx`を5秒以内**に返せば成功と
見なされる。**`3xx`が成功に含まれる**ため、HTTPS redirectがhealth checkを素通ししてしまい、probeが
DBへ一度も到達しないまま常にhealthyを報告する事故が起こり得る——だから§3の確認では、redirectでは
なく**本文`ok`の200**であることを確かめる。checkは起動時だけでなく**稼働中は数秒ごと**に送られ、
15秒失敗するとtrafficのルーティングが外れ、60秒失敗するとinstanceが自動再起動される。

## 1. Neonを作る

1. Neonでprojectを作り、regionはRenderに近いSingaporeを選ぶ。
2. production用database/userを作り、TLS必須のconnection stringを取得する。
3. connection stringをローカルファイルへ保存せず、次項のRender secret `DATABASE_URL`へ直接渡す。
4. accountとsessionを失えない運用へ広げる前に、backup/exportと復元手順を別途決める。

## 2. Render Blueprintを作る

1. Render Dashboardで **New > Blueprint** を選び、このrepositoryを接続する。
2. Blueprint pathには既定のroot `render.yaml`ではなく、
   `projects/toyama-dining-radar/render.yaml` を指定する。
3. 公開対象は承認済み変更がmergeされたbranchを選ぶ。feature branchをproductionへ直結しない。
4. Blueprint previewで `free`、`singapore`、root directory、build/start command、`/healthz`を確認する。
5. `sync: false` の各項目へRender Dashboard上でsecretを入力する。**`sync: false` が入力を促すのは
   Blueprintの初回作成時だけであり、既存Blueprintの更新時は無視される**——後から変数を足す場合は
   Dashboardで直接設定する。

| Render key | 入力元・扱い |
|---|---|
| `DATABASE_URL` | NeonのTLS connection string |
| `HOTPEPPER_API_KEY` | 人間管理のprovider credential |
| `HOTPEPPER_SEARCH_LATITUDE` | 非公開の検索地点。表示・log出力禁止 |
| `HOTPEPPER_SEARCH_LONGITUDE` | 非公開の検索地点。表示・log出力禁止 |
| `HOTPEPPER_SEARCH_RANGE` | 現行環境と同じ非公開range。未指定ならapplication既定値 |
| `DJANGO_BOOTSTRAP_ORGANIZER_USERNAME` | 初回だけ使うorganizer名 |
| `DJANGO_BOOTSTRAP_ORGANIZER_PASSWORD` | 十分に長い初回password |

`DJANGO_SECRET_KEY`はBlueprintが生成する。Renderが供給する`RENDER`と
`RENDER_EXTERNAL_HOSTNAME`を手入力しない。実値の形式と全変数は [env.example](env.example) を参照する。

## 3. 初回deployを確認する

buildはdependency install、`collectstatic`、migration、初回organizer作成、Django deployment checkの
順に失敗時停止で実行する。成功後、次を確認する。

1. `https://<Render host>/healthz` が本文`ok`で200を返す。
2. **`http://<Render host>/healthz` も、redirectではなく本文`ok`の200を返す**。ここが301だと、
   Renderのhealth checkは`3xx`を成功と見なすためprobeがDBへ到達しないまま緑になる。
3. `http://<Render host>/` がHTTPSへredirectされる（`/healthz`以外は従来どおり強制redirect）。
4. 初回organizerでsign inでき、候補画面、地図、同一origin static asset、OSM attributionが表示される。
5. 候補画面に `Powered by ホットペッパーグルメ Webサービス` のクレジットが
   `http://webservice.recruit.co.jp/` へのリンクつきで出ている（provider側の必須要件）。
6. responseにHSTS、content-type nosniff、frame deny、適切なReferrer-Policyがあり、session cookieが
   Secure / HttpOnly / SameSite=Laxである。
7. browser、URL、HTML、Render log、Neon logにAPI key、検索地点、距離、経路、徒歩時間が出ていない。
8. `/healthz`がprovider APIを呼ばず、DB障害時は秘密値を含まない503だけを返す。

sign in確認直後に、Renderから`DJANGO_BOOTSTRAP_ORGANIZER_USERNAME`と
`DJANGO_BOOTSTRAP_ORGANIZER_PASSWORD`を削除して再deployする。既存accountのpasswordや権限は
bootstrap commandでは上書きされない。

## 4. 運用とrollback

- GitHub checks通過後だけauto-deployする。Render/Neonの無料枠停止、上限、規約変更を定期的に確認する。
- **外形監視やkeep-alive pingerでRenderを起こし続けない。** health checkは稼働中に数秒ごとDBへ
  `SELECT 1`を投げるため、Renderが起きている間Neonのcomputeも起きたままになる。Renderが15分の
  idleでspin downすることが、Neonの100 CU時間/月を守っている唯一の仕組みである。常時稼働させると
  最小0.25 CUでも月182 CU時間相当となり、月の途中でNeonのcomputeが止まる。cold startを嫌って
  pingerを足すと、無料構成そのものが成立しなくなる。
- health checkが60秒失敗するとRenderはinstanceを自動再起動する。再起動が繰り返される場合は、
  applicationではなくNeon側（suspend復帰の遅延・上限到達）をまず疑う。
- provider規約の要点（2026-08-12再確認）: クレジット表示は必須で、飲食店から金銭等の対価を得る
  ビジネスに関わるサイトでの利用は禁止されている（affiliate収益は可）。APIリファレンスと
  ご利用案内はcacheや請求回数の上限を定めていない——本製品のno-cache方針はproviderの要求ではなく
  こちらの選択である（ADR-0018）。
- applicationだけの不具合はRenderの直前成功deployへrollbackする。schema変更を含む場合は、先に
  migrationの後方互換性とDB復元方法を確認する。
- `DATABASE_URL`、provider key、検索地点、初回passwordが漏えいした疑いがあれば、公開を止めて
  該当credentialをrotateする。git履歴へ入った場合は値の削除だけで解決したと扱わない。
- custom domainを追加する場合は`DJANGO_ALLOWED_HOSTS`へhost名だけを追加し、HTTPS、CSRF、cookie、
  HSTSを再確認する。
