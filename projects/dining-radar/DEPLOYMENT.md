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
   `projects/dining-radar/render.yaml` を指定する。
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

## 7. ECS Fargate + ALBへの移行先（KEN-31、KEN-37）

Web（このRender構成）をECS Fargate単一タスク（0.25vCPU/0.5GB）へ移し、前段にALBを置く。ALBが
ACM証明書でTLSを終端し、`/livez`でタスクを監視する。DB（Neon）は変更しない。コード側の成果物
（Dockerfile・タスク定義・サービス定義・デプロイスクリプト・CloudWatchアラーム定義）は
[deploy/](deploy/README.md)、作成済みリソースの一覧と削除手順は [deploy/RESOURCES.md](deploy/RESOURCES.md)。

**この節は [ADR-0067](adr/0067-consider-aws-deployment-migration.md) の「ALB無し・Elastic IP付け替え」
を置き換える。** 実機（KEN-37）で、Fargateのタスクのrequester-managed ENIへ`AssociateAddress`すると、
管理者権限でも`AuthFailure`になり、その方式が成立しないと分かった（Fargateのタスクには静的IPや
Elastic IPを付けられない）。ADRの差し替えはarchitectの仕事として別に起票する。

**「AWS側」と明記した手順は人間が実行する。**このリポジトリのAI実行系はAWS認証情報を持たない。

### 前提と注意

- 料金（東京、常時稼働、2026-09-30 AWS Price Listの値）: Fargate 約$11 + ALB 約$18 + ALBの公開IPv4（2AZ）
  約$7 + タスクの公開IPv4 約$4 + LCU 〜 **月$40前後**。ADR-0067の「月$4〜5」は過小だった。
  ALBは作った時点から課金が始まる。課金されるものは、動作確認の準備が整ってから最後に作る。
- **Neon FreeのCU時間（月100）を守る**。常時稼働のプローブがDBへ`SELECT 1`を投げ続けると、Neonが
  一度も休めず約18日で枠を使い切る（§4）。ALBとコンテナ内のヘルスチェックは、DBに触れない
  `/livez`を使う。DB確認つきの`/healthz`は手動の確認用に残す。
- ALBのヘルスチェックは`Host`にターゲット自身のIPを入れて送る（コンテナ内は`localhost`）。
  `HealthCheckMiddleware`が`/healthz`・`/livez`だけを`Host`検証の前に答える。
- 作る順序（課金とやり直しを減らす）: 1〜5（無料） → 6（ALB。課金開始） → 7（サービス）。

### 7-1. イメージをECRへ積む（AWS側）

1. ECRリポジトリ`dining-radar-web`を作る（`--image-tag-mutability IMMUTABLE`、`scanOnPush=true`）。
2. `deploy/deploy.sh`がbuild・push・タスク定義登録・サービス更新・安定待ちを行う（初回はサービスが
   無いので、7-5でサービスを作った後に使う）。手で行う場合は`projects/dining-radar/`をコンテキストに、
   タグはgitのコミットIDにする（ECRのタグは上書きできない）。
   ```
   podman build --platform linux/amd64 --format docker -t <registry>/dining-radar-web:<commit> .
   podman push <registry>/dining-radar-web:<commit>
   ```
3. `manage.py check --deploy`、`migrate`は`docker-entrypoint.sh`がコンテナ起動のたびに走らせる。

podmanをrootlessで使う環境の注意: systemdのユーザーセッションが無いと`/run/user/<uid>`が無く
`crun`が失敗する。`sudo loginctl enable-linger <user>`と、`~/.config/containers/containers.conf`に
`[engine]`・`cgroup_manager = "cgroupfs"`が要ることがある。Docker Hubの短い名前（`caddy`など）は
`podman pull docker.io/library/...`で先に取る。

### 7-2. secretをSSM Parameter Storeへ入れる（AWS側）

`deploy/ecs/task-definition.json`の`secrets`が参照するSSM Parameter Store（Standard・SecureString）
パラメータを作る。Secrets Managerは使わない（$0.40/secret/月を避ける）。値は`read -rs`で入力し、
コマンド履歴・画面・チャットに残さない。**SSMは空の値を保存できず、タスク定義は全パラメータの存在を
要求する**。

| SSMパラメータ名（`/dining-radar/prod/`の下） | 入力元・扱い |
|---|---|
| `django_secret_key` | 新規に生成（Renderの値とは別でよい） |
| `django_allowed_hosts` | 公開ホスト名（カンマ区切り）。§5と同じ理由で文書・git・issueに書かない |
| `database_url` | NeonのTLS connection string |
| `hotpepper_api_key` | 人間管理のprovider credential |
| `hotpepper_search_latitude` / `_longitude` | 非公開の検索地点。表示・log出力禁止 |
| `hotpepper_search_range` | 未指定ならアプリ既定値（`3`）と同じ値を入れる |
| `django_bootstrap_organizer_username` / `_password` | §6の仕組み。DBに既存のorganizerがあるなら、その名前と**使われないランダムなpassword**を入れる（同名があれば何も作られず、passwordも上書きされない）。存在しない名前を入れるとログインできるaccountが作られる |

### 7-3. ネットワークとIAM（AWS側）

1. デフォルトVPCのパブリックサブネットを使う。セキュリティグループを2つ作る。
   - ALB用: inbound TCP 80・443を`0.0.0.0/0`から。
   - タスク用: inbound **TCP 8000を、ALB用グループからだけ**（送信元にグループを指定する）。
2. ECS実行ロール`dining-radar-ecs-execution`: 信頼ポリシー`ecs-tasks.amazonaws.com`、管理ポリシー
   `AmazonECSTaskExecutionRolePolicy`、インラインポリシーで`ssm:GetParameters`
   （`parameter/dining-radar/prod/*`）と`logs:CreateLogGroup`（`/dining-radar/prod/*`、タスク定義が
   `awslogs-create-group`を使うため管理ポリシーに無い権限が要る）。SecureStringの既定鍵
   （`aws/ssm`）の復号には追加のKMS権限は要らない。
3. タスク定義を登録する。`<AWS_ACCOUNT_ID>`・`<AWS_REGION>`・`<TAG>`を置換したコピーを作って
   `aws ecs register-task-definition --cli-input-json file://...`（リポジトリのファイルは直さない）。
4. ECSクラスタ`dining-radar`を作る。

### 7-4. 証明書（ACM）とターゲットグループ（AWS側）

1. ACMで公開ホスト名の証明書を要求する（`--validation-method DNS`）。ACMが示す検証用CNAMEを
   Route 53へ作る（更新のため残す）。`ISSUED`になるまで数分〜30分。
2. ターゲットグループを作る: HTTP 8000、`--target-type ip`、ヘルスチェック`/livez`・
   `--matcher HttpCode=200`、`deregistration_delay.timeout_seconds=30`（再デプロイを速くする）。

### 7-5. ALBとサービス（AWS側。ここから課金が始まる）

1. ALBを作る（internet-facing、2つ以上のAZのサブネット、ALB用セキュリティグループ）。リスナーは
   443（ACM証明書、既定アクションでターゲットグループへforward）と80（443へ301）。
2. サービスを作る。`deploy/ecs/service-definition.json`の`<TARGET_GROUP_ARN>`・`<PUBLIC_SUBNET_ID>`・
   `<SECURITY_GROUP_ID>`を置換して`aws ecs create-service --cli-input-json file://...`。
   `minimumHealthyPercent: 100`・`maximumPercent: 200`で、新しいタスクが健康になってから古いタスクを
   止める（無停止）。`deploymentCircuitBreaker`が失敗した入れ替えを自動で戻す。**既存サービスへ
   ALBの設定は足せない場合があるので、必要なら作り直す**（同名のサービスは旧サービスが
   `INACTIVE`になるまで作れない）。
3. `aws elbv2 describe-target-health`でタスクが`healthy`になることを確認する。

### 7-6. DNSと確認（AWS側）

1. Route 53でホスト名のAレコードを**ALIAS**としてALBへ向ける（ALIASのゾーンIDはALB側の
   `CanonicalHostedZoneId`）。
2. §3の手順（HTTPS redirect・セキュリティヘッダ・organizer sign in・Hot Pepperクレジット・OSM
   attribution・session cookie）を同じ基準で確認する。
3. 動作を確認できたら、Render側のサービスを止める（削除は即座に行わない。切り戻し経路になる）。
   Renderにカスタムドメインを置いていたなら、先にRender側の登録を外してからRoute 53のCNAMEを消す。
4. Neon（Neonのコンソール）で、CU時間が増え続けていないこと（コンピュートがIdleになる時間がある
   こと）を確認する。

### 7-7. 以後のデプロイ（AWS側）

`AWS_PROFILE=<profile> deploy/deploy.sh`（コミット済みの作業ツリーから）。タグはコミットID、
ECRに同じタグがあればbuild・pushを省く。失敗した入れ替えはサーキットブレーカーが前の版へ戻し、
スクリプトは非ゼロで終わる。

### 7-8. CloudWatch（AWS側）

- ログはタスク定義の`awslogs`ドライバが`/dining-radar/prod/web`へ送る。保持期間は既定が無期限なので
  14日などに設定する（`aws logs put-retention-policy`）。
- 基本アラーム2件（タスクCPU・メモリ）は`bash deploy/cloudwatch/create-alarms.sh`で作る。通知先
  （SNSトピック）は未決定のため未設定。

### 既知のトレードオフ

- 常時稼働の料金が月$40前後になる。学習目的の暫定構成であり、より安い構成（Lightsail・EC2・
  Render等）への移行を別チケットで検討する。
- ALBがあるのでAWS WAFを後から付けられる。招待制・署名付き使い捨てリンクのみの運用で、
  公開signup/フォームは無い。
- `deploy/caddy/`と`deploy/lambda/reattach_elastic_ip/`は、ALB無しの代替構成（タスクの公開IPを
  Route 53へ反映する、EC2上で動かす等）の素材として残してある。この構成では使わない。
