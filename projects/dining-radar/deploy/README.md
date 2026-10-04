# deploy/ — ECS Fargate + ALB の公開用成果物

[KEN-31](../DEPLOYMENT.md)・KEN-37 の、コード側の成果物。実リソースを作る人間向けの手順は
[DEPLOYMENT.md](../DEPLOYMENT.md) §7 が持ち、この文書は「何がここにあり、なぜあるか」の索引だけを
持つ（手順は複製しない、P-04）。作成済みのAWSリソースと削除手順は [RESOURCES.md](RESOURCES.md)。

構成: ALB（ACM証明書でTLS終端）→ ターゲットグループ（`/livez`）→ Fargateタスク（Djangoのみ、8000番）。
当初のADR-0067（ALB無し・Elastic IP付け替え）は、Fargateのタスクにelastic IPを付けられず実機で成立
しなかったため、この構成に置き換えた。

## 使うもの

| パス | 役割 |
|---|---|
| `deploy.sh` | イメージのbuild→ECR push→タスク定義登録→サービス更新→安定待ちを1本で行う。タグはコミットID、作業ツリーはコミット済みであること |
| `docker-entrypoint.sh` | アプリコンテナのENTRYPOINT（`../Dockerfile`）。起動のたびに`migrate`・`provision_organizer --if-configured`・`check --deploy`を実行してからgunicornを起動する |
| `ecs/task-definition.json` | `aws ecs register-task-definition --cli-input-json`の入力。webコンテナ1つ、0.25vCPU/0.5GB、secretsはSSM Parameter Store（値は載せない）。ヘルスチェックはDBに触れない`/livez` |
| `ecs/service-definition.json` | `aws ecs create-service --cli-input-json`の入力。ターゲットグループにつなぎ、100/200で無停止に入れ替え、サーキットブレーカーで失敗を自動で戻す |
| `cloudwatch/alarms.json`、`cloudwatch/create-alarms.sh` | タスクのCPU・メモリの基本アラーム2件。通知先は未決定 |
| `RESOURCES.md` | 作成済みAWSリソースの台帳（課金されるもの、削除手順、月次の確認コマンド） |

## 使わないもの（ALB無しの代替構成の素材として残す）

| パス | 何か |
|---|---|
| `caddy/` | TLS終端のサイドカー。ALBがTLSを終端するこの構成では不要。ALB無しでEC2やタスクの公開IPを直接公開する構成では使える |
| `lambda/reattach_elastic_ip/` | Elastic IPをタスクのENIへ付け替えるLambda。**Fargateのタスクには付けられず動かない**（EC2インスタンスへ付ける構成なら不要）。タスクの公開IPをRoute 53へ反映する構成の叩き台にはなる |

`<PLACEHOLDER>`はすべて環境固有（アカウントID、リージョン、サブネット・セキュリティグループ・
ターゲットグループのID、イメージのタグ）で、AWSリソースができるまで分からない。使う時点で人間が
置換する（`deploy.sh`はタスク定義の分を自動で置換する）。いずれもsecretではない。
