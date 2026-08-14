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
DBへ一度も到達しないまま常にhealthyを報告する事故が起こり得る——`settings.py`が`/healthz`だけを
`SECURE_REDIRECT_EXEMPT`に入れているのはこのためである。**この経路は公開インターネットからは観測
できない**（Renderのedgeが平文HTTPを先に終端するため）。確認方法は§3-3を参照する。checkは起動時
だけでなく**稼働中は数秒ごと**に送られ、15秒失敗するとtrafficのルーティングが外れ、60秒失敗すると
instanceが自動再起動される。

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

1. `https://<host>/healthz` が本文`ok`で200を返す。
2. `http://<host>/` がHTTPSへredirectされる。
3. **`/healthz`の免除が効いているかは、公開インターネットからは確認できない。** Renderのedgeが平文
   HTTPを先に終端して301を返すため、`http://<host>/healthz` は必ず301になり、リクエストはgunicornへ
   届かない（実測: 301応答にはDjangoのヘッダが一つも無く `x-render-origin-server` も付かない。
   200応答には両方ある）。**この301はDjangoの`SECURE_SSL_REDIRECT`ではないので、免除の失敗を意味
   しない。** health checkはedgeを通らずportへ直接届くので、外形からは観測できない経路である。

   **確認するにはgunicornのaccess logを一時的に出す。** Render → Settings → Start Command を編集して
   末尾に `--access-logfile -` を足す（`render.yaml`を変えずDashboardの上書きで済む）。再deploy後、
   Logsに数秒ごと`/healthz`の行が出る。見るのはステータスコードだけである。

   - `"GET /healthz HTTP/1.1" 200 2` … 免除が効いている。応答2バイトは本文`ok`＝ビュー自身の応答で
     あり、`SELECT 1`が実行されている。送信元がRFC1918のprivate addressでUAが`Render/1.0`であること
     も併せて確認する（edgeを迂回している証拠になる）。
   - `"GET /healthz HTTP/1.1" 301` … 免除が効いていない。probeは素通りしており、DBが落ちても
     healthyと報告される。

   確認後はStart Commandを元へ戻す。数秒ごとのログで無料枠のログ保持を埋めないためである。

   **Neonのcompute表示で代用しようとしないこと。** 一度試して失敗している——グラフの時間解像度が粗く、
   ユーザーのアクセス・orchestratorの検証アクセス・health checkが同じ線に混ざるため、ActiveとIdleの
   切り替わりから5分閾値と15分閾値を区別できない。「接続していそう」以上の判定ができない。
4. 初回organizerでsign inでき、候補画面、地図、同一origin static asset、OSM attributionが表示される。
5. 候補画面に `Powered by ホットペッパーグルメ Webサービス` のクレジットが
   `http://webservice.recruit.co.jp/` へのリンクつきで出ている（provider側の必須要件）。
6. responseにHSTS、content-type nosniff、frame deny、適切なReferrer-Policyがあり、session cookieが
   Secure / HttpOnly / SameSite=Laxである。
7. browser、URL、HTML、Render log、Neon logにAPI key、検索地点、距離、経路、徒歩時間が出ていない。
8. `/healthz`がprovider APIを呼ばず、DB障害時は秘密値を含まない503だけを返す。

sign in確認直後に、Renderから`DJANGO_BOOTSTRAP_ORGANIZER_USERNAME`と
`DJANGO_BOOTSTRAP_ORGANIZER_PASSWORD`を削除して再deployする。既存accountのpasswordや権限は
bootstrap commandでは上書きされない。キーを残して値だけ空にしてもよい——同じ仕組みを2人目以降の
招待にも使うため、詳細と注意点は§6にまとめてある。

## 4. 運用とrollback

- GitHub checks通過後だけauto-deployする。Render/Neonの無料枠停止、上限、規約変更を定期的に確認する。
- **外形監視やkeep-alive pingerでRenderを起こし続けない。** health checkは稼働中に数秒ごとDBへ
  `SELECT 1`を投げるため、Renderが起きている間Neonのcomputeも起きたままになる。Renderが15分の
  idleでspin downすることが、Neonの100 CU時間/月を守っている唯一の仕組みである。常時稼働させると
  最小0.25 CUでも月182 CU時間相当となり、月の途中でNeonのcomputeが止まる。cold startを嫌って
  pingerを足すと、無料構成そのものが成立しなくなる。
- health checkが60秒失敗するとRenderはinstanceを自動再起動する。再起動が繰り返される場合は、
  applicationではなくNeon側（suspend復帰の遅延・上限到達）をまず疑う。
- provider規約の要点（2026-08-12確認、2026-08-14訂正）: クレジット表示は必須で、飲食店から金銭等の
  対価を得るビジネスに関わるサイトでの利用は禁止されている（affiliate収益は可）。
  **cacheについては利用規約（`regulation.html`）に明文の規定がある**——ご利用案内が個別に定めない
  場合、`キャッシュの更新頻度を24時間以内と定めます`。取得した情報を第三者のデータベースへ複製保存
  することも禁じられている（同一originのブラウザ内`sessionStorage`はこれに当たらない）。
  **2026-08-12の記録は「cacheの上限は定められていない」としていたが誤りだった**——APIリファレンスと
  ご利用案内だけを読んで否定を記録し、利用規約本体も、**この条項を2026-08-09から全文引用していた
  `adr/0018`（本プロジェクト自身の規約検討ADR）も読んでいなかった**。外部規約について「無い」と
  書く前に、まずリポジトリ内の該当ADRを読むこと。したがって、ブラウザに保持するprovider由来の
  値には24時間以下の期限を必ず設ける（ADR-0018・ADR-0024）。
- applicationだけの不具合はRenderの直前成功deployへrollbackする。schema変更を含む場合は、先に
  migrationの後方互換性とDB復元方法を確認する。
- `DATABASE_URL`、provider key、検索地点、初回passwordが漏えいした疑いがあれば、公開を止めて
  該当credentialをrotateする。git履歴へ入った場合は値の削除だけで解決したと扱わない。

## 5. custom domainを足す（順序を守らないとサイトが落ちる）

Renderのdocumentationはこう定めている——**verifiedなcustom domainがあると、HTTP health checkの
`Host`ヘッダはそのdomainになる**（無ければサービスの`onrender.com` subdomain）。一方、実測のとおり
`ALLOWED_HOSTS`に無いHostは**400**を返す。

`settings.py`の`ALLOWED_HOSTS`は`DJANGO_ALLOWED_HOSTS`とRenderが供給する`RENDER_EXTERNAL_HOSTNAME`
だけで組まれ、**custom domainはどちらにも入らない**。したがってdomainを先にverifyすると、health check
が全て400になり、15秒でrouting除外、60秒でinstance自動再起動——これが延々と続く。

必ずこの順で行う。

1. Render Dashboard → Environment → **`DJANGO_ALLOWED_HOSTS`** を追加する。値はhost名だけ（scheme・
   port・pathを付けない。複数ならカンマ区切り）。`render.yaml`には無い変数なのでDashboardで足す。
   `RENDER_EXTERNAL_HOSTNAME`は実装が別途追加するため、この変更は純粋な追加であり既存originを壊さない。
2. 再deploy後、既存の`onrender.com` URLがまだ動くことを確認する。
3. **その後で** Render → Settings → Custom Domains でdomainを追加する。Renderが向け先を表示するので、
   その値を使う（推測しない）。
4. DNSにレコードを作る。**subdomainを勧める**——CNAMEを向けるだけで済み、先方のIP変更にも自動で追従する。
   apexはDNS仕様上CNAMEを置けず、Route 53のALIASはAWSリソース専用でRenderには向けられないため、
   Renderが示すA レコードのIPを直書きすることになり、IP変更を自分で追う必要が生じる。
5. verified後、TLS証明書はRenderが自動発行・更新する（Let's Encrypt）。wildcardでなければ
   `_acme-challenge`の追加レコードは要らない。
6. HTTPS、CSRF、cookie、HSTSを§3の手順で再確認する。

自前のdomainを持つとHSTSの`includeSubDomains`とpreloadが初めて選択肢になる。ただしpreloadは取り消しが
難しいため、採用するなら独立した判断とADRの対象にする。既定は現状どおり両方offである。

## 6. organizerを追加する・ログインできなくなったときに戻す

無料RenderにはShellが無く、`createsuperuser`を叩く場所が存在しない。そのため`build.sh`は毎回
`manage.py provision_organizer --if-configured`を実行し、**環境変数からaccountを作る**。この仕組みは
初回だけのものではなく、**2人目以降の招待手段としてそのまま使える**。

### 挙動（`provision_organizer`）

| `DJANGO_BOOTSTRAP_ORGANIZER_USERNAME` / `_PASSWORD` | 動作 |
|---|---|
| 両方が空（またはキーごと不在） | 何もせず正常終了する（`--if-configured`） |
| 両方に値があり、同名accountが無い | 作成する（`is_staff=False` / `is_superuser=False`） |
| 両方に値があり、同名accountが既にある | **何もしない。passwordも権限も上書きしない** |
| 片方だけに値がある | `CommandError`。`build.sh`は`errexit`なのでbuildが落ちる |

**キーを残して値を空にするのと、キーごと消すのは同じ挙動である**——実装は`os.environ.get(..., "")`で
読むため、未設定と空文字を区別しない。キーを残すほうが次回の変数名を覚えずに済む。ただし
`_PASSWORD`は`strip()`されないため、**空白文字を1つでも残すと「設定されている」と判定され**、
username側が空ならbuildが落ちる。消すときは完全に空にする。

### 2人目以降を招待する

1. 2つの変数へ**新しい人のusernameとpassword**を入れる。passwordはDjangoの検証4種
   （8文字以上・username非類似・一般的でない・数字のみでない）を通る必要がある。落ちる場合は
   `python tools/check_organizer_password.py` が理由を出す（passwordはechoせずargvにも取らない）。
2. 再deployする。buildの`provision_organizer`がaccountを作る。
3. 本人に初回sign inしてもらい、画面のpassword変更で**本人だけが知る値へ変えてもらう**。
4. **2つの値を空にして**再deployする。

既存accountには一切触らないため、この4手順は何度繰り返しても安全である。手順4を忘れても機能は
壊れないが、**ログインできる生のpasswordがRender Dashboardに残り続ける**——それが手順4の唯一かつ
十分な理由である。

### まとめて発行する（再deployなし）

1人につき1回の再deployは、人数が増えると割に合わない。`manage.py`は`test`以外のコマンドでは本番
settings module（`dining_radar.settings`）を使うため、**ローカルから同じcommandをNeonへ向けて実行
できる**。Render側の環境変数は触らず、deployも起きない。

```bash
read -rsp 'DATABASE_URL: ' DATABASE_URL && export DATABASE_URL
export DJANGO_SECRET_KEY='local-only-not-the-production-key'

export DJANGO_BOOTSTRAP_ORGANIZER_USERNAME='<username>'
read -rsp 'password: ' DJANGO_BOOTSTRAP_ORGANIZER_PASSWORD && export DJANGO_BOOTSTRAP_ORGANIZER_PASSWORD
python manage.py provision_organizer
```

`read -rs`を使うのはshell履歴へ実値を残さないためである。`DJANGO_SECRET_KEY`はダミーでよい——
**passwordのhash化に`SECRET_KEY`は使われない**（PBKDF2とuserごとのsalt）。3〜5行目をusernameと
passwordを変えて繰り返す。

**`DATABASE_URL`のexportを忘れると、警告なくローカルのSQLiteへ作られる。** `settings.py`は`RENDER`が
無い環境ではDATABASE_URLを必須にせず、`settings_base`のSQLiteへ落ちるためである。実行前に接続先を
確かめること。

```bash
python manage.py shell -c "from django.db import connection; print(connection.settings_dict['ENGINE'], connection.settings_dict.get('HOST'))"
```

`postgresql`とNeonのhost名が出れば正しい。`sqlite3`が出たらexportが効いていない。作成後は
`python manage.py shell -c "from django.contrib.auth import get_user_model; print(get_user_model().objects.count())"`
で件数を確認する。

この経路は接続文字列をshellへ一時的に置く。§1-3が禁じているのは**ファイルへの保存**であり、
`.env.local`へ書くのは方針から外れる。作業後はshellを閉じる。

### passwordを忘れたとき

**アプリ側に回復手段は無い。** 意図的にそうなっている——公開signupもemail resetも提供せず
（TDR-AUTH-03）、bootstrap accountは`is_staff=False`なのでDjango adminも使えず、無料RenderにShellも
無い。**account発行や回復のためにaccountへ`is_staff`を与えないこと**——`/admin/`は公開originから
到達でき、そのlogin formはこのアプリのlogin throttle（TDR-AUTH-07）を通らない。staff accountを1つ
作ると、その未制限のlogin surfaceが特権入口に変わる。そして`provision_organizer`は同名accountのpasswordを**上書きしない**ため、変数へ新しいpasswordを
入れ直しても何も起こらない。

回復はDB側で行う。NeonのSQL Editorで当該userの行を消し（既定の`auth_user`テーブル）、上の招待手順で
作り直す。その人のsessionは無効になり、他のaccountには影響しない。**この操作中も、passwordの実値を
SQL、log、issue、PRへ書かないこと。** 行を消してから環境変数で作り直すのであって、SQLでpasswordを
書き換えるのではない。
