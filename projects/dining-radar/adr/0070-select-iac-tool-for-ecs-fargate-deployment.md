---
id: 0070
scope: project/dining-radar
status: 提案中
date: 2026-10-05
approved_by: null
supersedes: []
superseded_by: null
relates_to: [P-04, P-05, P-08, ADR-0021, ADR-0067]
---

# ADR-0070: ECS Fargate構成（ADR-0067）の管理にIaCツールを採るか、採るなら何にするかを選ぶ

> **承認者向けサマリ**: `adr/0067`が決めたECS Fargate構成を、いまは`deploy/**`のJSON/シェル/Python
> ＋`DEPLOYMENT.md` §7の手作業手順で運ぶ（KEN-31）。これを**IaC（コードでインフラを宣言する道具）**に
> 移すかを、3案（A Terraform／B AWS CDK／C 現状維持）で比較して**提案**する。**起草者の推奨はA
> （Terraform。ライセンス上の懸念が重いならOpenTofuで同じ書き方）**。理由は、(1) 本構成は
> 約12種類の小さな資源で、抽象化層（CDK）の利得が小さいこと、(2) 既存資源をそのまま取り込む
> `import`が宣言的で、差分（plan）を人間が読んで承認する運用がこのリポジトリの「人間は4点で承認」の
> 流儀に合うこと、(3) ECSの構成要素が1対1でコードに見えるので、`adr/0067`の学習目的を損なわないこと。
> ただしCDKはPython/TypeScriptで書けて本体がDjangoのPythonと言語を揃えられ、Cは追加の道具・状態管理が
> 要らないという実利があり、**決めるのは人間**。本ADRは決定を下さず、承認は人間がPR上で行う。
> AWSの実リソースは作らず触らない（KEN-37の領分）。`deploy/**`・コードも変更しない。

## 文脈

### 0. 検証の申告（meta/adr/0039）

実際に`Read`した: `adr/0067`（全文）、`adr/0069`（書式）、`DEPLOYMENT.md`（§1〜§7の見出しと§7全文）、
`deploy/README.md`、`deploy/`のファイル一覧、`.github/workflows/`（govlint・採番検査の存在）。
確認していない／していないもの: `deploy/**`の各ファイルの中身（READMEと`DEPLOYMENT.md` §7の記述から
読んだ）、AWS上の実リソース（作らず触らない）、Terraform・CDK・OpenTofuの現行バージョンの仕様・
料金・ライセンス条項（**下記の道具についての記述は起草者の知識に基づく一般的な記述で、最新の公式
文書で裏を取っていない。承認前の確認事項に挙げる**）。

### 1. 経緯

- `adr/0067`が、WebをECS Fargate単一タスク（Caddyサイドカー、Elastic IP自動付け替え、CloudWatch、
  SSM Parameter Store、ECR）へ移すと決めた。KEN-31がコード側の成果物を`deploy/**`に置き、
  `DEPLOYMENT.md` §7が「AWS側」と明記した手順を**人間がコンソール/CLIで実行する**形にした。
- 実リソースの作成はKEN-37が受け持つ（本ADRの範囲外）。その作り方（手でCLIを打つ／IaCで作る）を
  先に決めておかないと、手で作った資源を後からIaCへ移す二度手間が生じうる。これが本ADRの動機。
- 管理対象の資源は、`adr/0067`・`DEPLOYMENT.md` §7・`deploy/README.md`から数えると次のとおり:
  ECRリポジトリ2、ECSクラスタ・タスク定義・サービス、セキュリティグループ、Elastic IP、
  Lambda関数＋実行ロール＋IAMポリシー、EventBridgeルール＋ターゲット＋Lambdaのリソースベース許可、
  CloudWatchロググループ・アラーム3、SSM Parameter Store（SecureString約12本）、Route 53のAレコード
  （ホストゾーンは既存）。VPC・サブネットは既存のデフォルトVPCを使う想定（`DEPLOYMENT.md` §7-3）。

### 2. 比較の軸

1. この構成（小さく、単一環境）に対する書く量・読みやすさ
2. 既存資源のimport（取り込み）のしやすさ
3. 状態の持ち方と、その壊れやすさ
4. 秘密値の扱い（`adr/0067`決定8・`DEPLOYMENT.md` §7-2の運用を壊さないか）
5. 追加で必要になる道具・権限・費用
6. 人間承認の流儀（変更の差分を人間がPR上で読めるか）との相性
7. KEN-31成果物（`deploy/**`）の移行コスト

## 検討した案

### A. Terraform（または互換のOpenTofu）

- **書き方**: HCLで資源を宣言する。ECSタスク定義は現行`task-definition.json`をほぼそのまま
  `container_definitions`に載せられ、移行の書き写しが機械的。
- **import**: 既存資源を`import`ブロック（Terraform 1.5以降の機能。起草者の知識、要確認）で取り込み、
  `plan`の差分が空になることで「コードと実物が一致した」と確かめられる。実物を一切変えずに
  取り込める。
- **状態**: tfstateが必要。ローカル保管は紛失・競合の危険があり、S3（＋ロック）に置くのが普通で、
  その**状態用バケット自体は先に手で作る**（鶏と卵）。状態に資源のIDや属性が入る。
- **秘密値**: `aws_ssm_parameter`に値を渡すと**値がtfstateへ平文で入る**。したがって秘密の値は
  IaCの外（人間が`put-parameter`）に置き、IaCは名前（ARN）だけを参照するのが安全。
- **追加の道具**: `terraform`（または`tofu`）CLI、状態用S3、実行用のIAM。費用は状態バケットの
  数セント程度の見込み（要確認）。
- **ライセンス**: TerraformはBSLに変わった経緯があり、個人の小規模利用に実害は小さいが、気になる
  なら互換のOpenTofu（OSS）を使え、HCLはそのまま。この選択は確認事項に挙げる。
- **承認との相性**: `plan`出力をPRに貼り、人間が差分を読んで承認する形を作りやすい。

### B. AWS CDK

- **書き方**: Python/TypeScript等で資源を組み立てる。本体がDjango（Python）なので言語は揃えられる。
  高水準の部品（ECSパターン等）を使えば短く書けるが、本構成は**ALB無し・サイドカー・
  Elastic IP付け替え**という非標準の形で、高水準部品の恩恵は小さく、低水準で書くことになりやすい
  （起草者の見立て）。
- **import**: 内部でCloudFormationへ合成される。既存資源の取り込みはCloudFormationのimport機能に
  なり、**取り込める資源の種類・手順に制約があり、Terraformより手間がかかる**と起草者は理解している
  （要確認）。
- **状態**: 状態はCloudFormationスタックがAWS側に持つので、自前の状態バケットは要らない。ただし
  `cdk bootstrap`（ステージング用のS3・ロールをアカウントに作る）が要り、これも実リソース。
- **秘密値**: SSMのSecureStringは、CloudFormation経由では作れない（既存パラメータの参照のみ）扱いが
  あるため、Aと同じく秘密値はIaCの外に置く運用になる（要確認）。
- **追加の道具**: Node.js＋CDK CLI、bootstrap用の資源。学習する対象が「ECS」に加えて「CDKの
  抽象とCloudFormation」に増える。
- **承認との相性**: `cdk diff`が差分を出す。Aと同等だが、合成後のCloudFormationとの二重の読みが要る。

### C. 現状維持（IaCを入れず`deploy/**`＋手順書で運ぶ）

- **書き方**: 追加なし。`DEPLOYMENT.md` §7を人間が実行する。
- **import**: 不要。ただし**「手順書と実物が一致しているか」を確かめる機械的な手段が無い**。
  `adr/0067`が帰結に挙げた「Lambdaが壊れどころになる」リスクへの備えも、手順書の実機確認に頼る。
- **状態**: 持たない。代わりに実物がAWS上にしかなく、再現（作り直し・環境複製）は手順の読み直し。
- **秘密値**: 現行どおり。問題なし。
- **追加の道具**: なし。費用も増えない。
- **承認との相性**: 差分の概念が無く、変更は手順書の文章とコンソール操作に散る（P-04の重複・ドリフトの
  温床になりうる）。
- **向く条件**: 資源がほとんど変わらず、作り直す予定も無く、学習対象をECSそのものに絞りたいとき。

### 比較表

| 軸 | A Terraform | B CDK | C 現状維持 |
|---|---|---|---|
| 書く量（本構成） | 中。タスク定義は書き写し | 中〜大。非標準形で高水準部品が効きにくい | 追加なし |
| 既存資源のimport | 宣言的、実物を変えずに一致を確認 | CloudFormation制約あり、手間が大きい | 不要（一致確認手段なし） |
| 状態 | tfstate（S3を先に手作り） | AWS側（bootstrapが必要） | なし |
| 秘密値 | 値を渡すとstateに平文。外に置く | 同様に外に置く運用（要確認） | 現行どおり |
| 追加の道具 | terraform/tofu、状態S3 | Node＋CDK、bootstrap | なし |
| 人間承認との相性 | planをPRで読める | diffを読める（二重の読み） | 差分概念なし |
| 学習の追加負荷 | HCL（小） | CDK＋CloudFormation（大） | なし |
| KEN-31成果物の移行 | 機械的な書き写し | 再表現が要る | 変更なし |

## 提案（決定ではない）

**起草者の推奨: A（Terraform。ライセンスが気になるならOpenTofu）。** ただし人間が決める。
以下は、Aが採られた場合に承認後の実装タスクが従う**方針案**であり、承認前は何も確定しない。

### 既存資源のimport方針（Aの場合）

1. **実物を変えない。** まずKEN-37で資源が作られた後（手で作られていても可）、`import`で取り込み、
   `plan`の差分が空になるまでコードを実物に合わせる。差分があるまま`apply`しない。
2. **順序は依存の少ない順**: ECR・ロググループ・Elastic IP → セキュリティグループ → IAM・Lambda →
   EventBridge（ルール・ターゲット・Lambdaのリソースベース許可は別資源で、`DEPLOYMENT.md` §7-4
   手順6の許可を取り込み忘れない）→ ECSクラスタ・タスク定義・サービス → CloudWatchアラーム。
3. **KEN-37より先にIaCを入れるなら、取り込みではなく最初からIaCで作る**ことも選べる。その場合も
   `apply`は人間が実行する（`adr/0021`・`adr/0067`の「外部状態変更は人間」を維持）。
4. **取り込まないもの**: RenderのBlueprint、Neon、既存Route 53ホストゾーン本体（`adr/0067`が流用と
   決めた既存資源）。Aレコードだけを管理対象にするかは確認事項に挙げる。
5. **秘密値はIaCの外**: SSMのSecureString（`/dining-radar/prod/**`）の値は人間が投入し、IaCは
   名前・ARNの参照だけを持つ（`DEPLOYMENT.md` §7-2の運用と、「secretをgit・stateに入れない」を保つ）。

### KEN-31成果物（`deploy/**`）の移行方針（Aの場合）

| 現行の成果物 | 移行後 |
|---|---|
| `ecs/task-definition.json`・`service-definition.json` | HCLの資源定義へ写す。`<PLACEHOLDER>`は変数・参照に置換される。JSONは移行完了後に削除か、IaCから`jsonencode`する単一の定義に統合（二重管理しない、P-04） |
| `lambda/reattach_elastic_ip/handler.py` | **残す**。コードでありIaCではない。Lambdaのzip化・デプロイだけをIaCが担う |
| `lambda/.../iam-policy.json`・`eventbridge-rule.json` | HCLの資源へ写す。JSONは移行完了後に削除か統合 |
| `cloudwatch/alarms.json`・`create-alarms.sh` | HCLの資源へ写し、スクリプトは削除 |
| `caddy/Dockerfile`・`Caddyfile`・`docker-entrypoint.sh`・`../Dockerfile` | **残す**（イメージの中身であってインフラ宣言ではない） |
| `deploy/README.md`・`DEPLOYMENT.md` §7 | IaC導入後は「JSONをCLIに渡す手順」から「`plan`を読み`apply`する手順」へ書き換える。人間が実行するという分担は変えない |

移行は**段階的**にし、IaCが実物と一致するまで既存の`deploy/**`と§7を捨てない（切り戻し経路の確保）。
Bを選ぶ場合は書き写しでなく再表現になり、Cを選ぶ場合は本表の変更が無い。

## 帰結（Aが承認された場合）

- 良い点: 実物とコードの一致が`plan`で機械的に確かめられる。作り直し・複製が再現可能になる。
  「Lambdaが壊れどころ」（`adr/0067`）の設定側のドリフトに気づける。
- 悪い点・代償: (1) tfstateという新しい壊れどころと、状態用S3の手作り（鶏と卵）。(2) 秘密値を
  IaCの外に置く運用の取り決め（stateへの流出防止）。(3) 学習対象がECSに加えてHCL・stateへ増える。
  (4) 状態バケット等で月数セント程度の追加費用の見込み（`adr/0067`同様、公式見積りで裏を取る）。
- Bが承認された場合: 上記(1)の代わりに`cdk bootstrap`が実リソースとして加わり、importの手間が増える。
  Cが承認された場合: 本ADRは「IaCを採らない」を記録して閉じ、`DEPLOYMENT.md` §7の手作業運用が続く。
- どの案でも: 実リソース作成・`apply`・secret投入は人間が行う（`adr/0021`・`adr/0067`の前例）。
  本ADRの承認自体はAWSに何も作らない。承認後に、(a) 選ばれた案の実装（別PR・別ticket）、(b) その時点の
  `deploy/**`・`DEPLOYMENT.md`の更新、が必要になる。本PRでは`deploy/**`もコードも変更していない。
- ルートの`activeContext.md`・プロジェクトの`activeContext.md`の更新は本ADRの所有範囲外で、
  orchestratorへの申し送りとする。

## 確認事項（人間に確認されたい）

1. **A/B/Cのどれを採るか**（起草者の推奨はA）。
2. Aなら**TerraformかOpenTofuか**。ライセンス（BSL）をどう評価するか。
3. 本ADR記載の道具の仕様・費用・ライセンスは起草者の知識に基づき**公式文書で裏を取っていない**。
   承認前に、`import`ブロックの対応バージョン、CDKのimport制約、SSMとCloudFormationの関係、状態バケットの
   費用を確認してよいか（`adr/0067`の料金留保と同じ扱い）。
4. IaCの導入時期: KEN-37の**前**（最初からIaCで作る）か**後**（手で作ってから取り込む）か。
5. Route 53のAレコードを管理対象にするか（ホストゾーン本体は管理対象外）。
6. 状態の保管先（S3）と、それを作る権限を持つ人（人間）の取り決め。
