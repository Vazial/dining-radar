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
5. `sync: false` の各項目へRender Dashboard上でsecretを入力する。

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
2. `http://<Render host>/` がHTTPSへredirectされる。
3. 初回organizerでsign inでき、候補画面、地図、同一origin static asset、OSM attributionが表示される。
4. responseにHSTS、content-type nosniff、frame deny、適切なReferrer-Policyがあり、session cookieが
   Secure / HttpOnly / SameSite=Laxである。
5. browser、URL、HTML、Render log、Neon logにAPI key、検索地点、距離、経路、徒歩時間が出ていない。
6. `/healthz`がprovider APIを呼ばず、DB障害時は秘密値を含まない503だけを返す。

sign in確認直後に、Renderから`DJANGO_BOOTSTRAP_ORGANIZER_USERNAME`と
`DJANGO_BOOTSTRAP_ORGANIZER_PASSWORD`を削除して再deployする。既存accountのpasswordや権限は
bootstrap commandでは上書きされない。

## 4. 運用とrollback

- GitHub checks通過後だけauto-deployする。Render/Neonの無料枠停止、上限、規約変更を定期的に確認する。
- applicationだけの不具合はRenderの直前成功deployへrollbackする。schema変更を含む場合は、先に
  migrationの後方互換性とDB復元方法を確認する。
- `DATABASE_URL`、provider key、検索地点、初回passwordが漏えいした疑いがあれば、公開を止めて
  該当credentialをrotateする。git履歴へ入った場合は値の削除だけで解決したと扱わない。
- custom domainを追加する場合は`DJANGO_ALLOWED_HOSTS`へhost名だけを追加し、HTTPS、CSRF、cookie、
  HSTSを再確認する。
