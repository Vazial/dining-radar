# AWSリソース台帳

AWS上に作った（作る）リソースの一覧。**作ったら必ず追記し、消したら状態を更新する**。解放漏れ（特に課金されるもの）を防ぐための台帳であり、手順は [DEPLOYMENT.md](../DEPLOYMENT.md) §7 が持つ。

書かないもの: アカウントID、実ドメイン、secretの値（`DEPLOYMENT.md`と同じ方針）。リージョンは特記が無ければ `ap-northeast-1`。全リソースに `Project=dining-radar` のタグを付ける。

最終更新: 2026-10-04（KEN-37）

## 現在の構成（暫定）

KEN-37の実機検証で、ADR-0067の「ALB無し・Elastic IP付け替え」は成立しないことが分かった（Fargateの
タスクのrequester-managed ENIにElastic IPを関連付けられない）。当面はALB + Fargateで動かし、
1〜2か月後に安い構成へ移す（移行用チケットで検討）。台帳の最終更新はKEN-37。

## 課金されるもの（解放漏れに注意）

| リソース | 名前 | 月額の目安 | 削除 |
|---|---|---|---|
| ECSサービス（Fargate 0.25vCPU/0.5GB） | `dining-radar` クラスタの `dining-radar-web` | 約$11 | `aws ecs delete-service --cluster dining-radar --service dining-radar-web --force` |
| タスクの公開IPv4 | （タスクの稼働中のみ） | 約$3.65 | タスクを止めれば消える |
| ALB | `dining-radar` | 約$17.7 + LCU | 下の削除順序を守る |
| ALBの公開IPv4（2AZ） | （ALBに付随） | 約$7.3 | ALBを消せば消える |

月額の合計は約$40前後（東京、常時稼働の概算）。

### ALBの削除順序

1. リスナー2つ（443・80） → 2. ALB → 3. ターゲットグループ → 4. セキュリティグループ（ALB用）。
サービスを先に消す（ターゲットグループが使用中だと消せない）。

## ほぼ無料のもの

| リソース | 名前 | 備考 |
|---|---|---|
| ECRリポジトリ | `dining-radar-web`（使用中）、`dining-radar-caddy`（不使用） | `caddy`は不要。イメージが増えたらライフサイクルで古いものを消す |
| SSM Parameter Store（SecureString、Standard） | `/dining-radar/prod/*` の11個 | `public_domain`・`acme_email` はCaddy専用で不要 |
| IAMロール | `dining-radar-ecs-execution`（使用中）、`dining-radar-reattach-eip`（不使用） | |
| Lambda | `dining-radar-reattach-eip`（不使用） | Fargateでは動かない |
| EventBridgeルール | `dining-radar-web-task-running`（不使用） | |
| ターゲットグループ | `dining-radar-web`（HTTP 8000、ヘルスチェック`/livez`） | |
| ACM証明書 | 公開ホスト名の1枚（DNS検証） | 検証用CNAMEは更新のため残す |
| セキュリティグループ | `dining-radar-alb`（80・443）、`dining-radar-web`（8000をALB用グループからだけ） | |
| ECSクラスタ、タスク定義 | `dining-radar`、`dining-radar-web`（版は増える） | タスク定義は削除ではなく登録解除（deregister） |
| CloudWatch Logsのロググループ | `/dining-radar/prod/web`（使用中）、`/dining-radar/prod/caddy`・`/aws/lambda/dining-radar-reattach-eip`（不使用） | 保持期間14日 |
| Route 53 | 公開ホスト名のAレコード（ALIAS → ALB）、ACM検証用CNAME | ホストゾーンは既存 |

解放済み: Elastic IP（2026-10-03。Fargateのタスクには付けられず、ALB構成でも不要）。

## リージョンに依らないもの

| リソース | 備考 |
|---|---|
| AWS Budgets | 月$25の予算（ルートユーザーで作成。通知のみ、止めない） |
| Route 53 | ホストゾーンとドメイン登録（既存） |
| IAM Identity Center（us-east-1） | 作業用ユーザーと権限セット。作業後に`AdministratorAccess`を絞る |

## 外部サービスの消費

| 対象 | 見るもの |
|---|---|
| Neon Free | 月100 CU時間。ヘルスチェックを`/livez`（DBに触れない）にして、コンピュートがIdleになることを確認する。10-04時点で15.93 CU時間消費済み |

## 定期確認（月1回）

次が**何も出ない**こと（出たら解放漏れ）。

```bash
aws elbv2 describe-load-balancers --query "LoadBalancers[].LoadBalancerName" --output text
aws ec2 describe-nat-gateways --query "NatGateways[?State!='deleted'].NatGatewayId" --output text
aws ec2 describe-instances --query "Reservations[].Instances[?State.Name!='terminated'].InstanceId" --output text
aws ec2 describe-volumes --query "Volumes[].VolumeId" --output text
aws ec2 describe-addresses --query "Addresses[?AssociationId==null].AllocationId" --output text
```

ALBを使っている間は1行目に`dining-radar`が出る（それ以外が出たら調べる）。Cost Explorerのサービス別課金も月1回見る。
